# Jeremy Dilatush - All rights reserved.
# bgpy_clnt.py - begun 27 April 2019
"""This is the "skeleton" of the bgpy BGP implementation in Python.
It provides a limited BGP tester that can connect to a BGP peer, exchange
open and keepalive messages as required, and perform other operations
(chiefly running "canned programmes" that might send BGP routes) as
requested on stdin.

This will probably not work on Windows because of how it uses 'select'."""

## ## ## Top matter

import socket
import sys
import time
import select
from traceback import format_exc, print_exc

from bgpy_misc import dbg
import bgpy_misc as bmisc
import bgpy_repr as brepr
import bgpy_oper as boper
from bgpy_prog import register_programmes

## ## ## Command interface on stdin

class Commanding(object):
    """Command interface of bgpy_clnt.  Handle commands that are meant
    to come in on stdin.  Each command takes up a line. One command is "help".
    It documents the others."""

    def __init__(self, client):
        "initialize the Commanding object"
        # programme_handlers maps the name of a programme to its handler; see
        # register_programme()
        # programme_iterators maps the name of a programme already started
        # to its iterator; see register_programme().
        # client is the client object to which the commands apply,
        # which will in turn be passed to programme handlers etc.
        # programme_iterator_times indicates when each should run; 0 means
        # immediately; None means it's suspended
        self.programme_handlers = dict()
        self.programme_iterators = dict()
        self.programme_iterator_times = dict()
        self.client = client

    def register_programme(self, pname, phandler):
        """Register a 'canned programme', with the given name, and a handler.
        The handler is to be called with the following parameters:
            this Commanding object
            the corresponding Client object
            a list of argument strings
        It generates an iterable.  That iterable, when next() is called on it,
        should do whatever's desired of the canned program, and yield
        one of the following:
            number -- time to wait until before doing next() again
            None -- Wait for an explicit "resume" command.
            boper.NEXT_TIME -- Run next time through the event loop, which might
                be right away, or long in the future after something
                else happens.  Use this if you're waiting for some special
                event, as:
                    while not has_my_event_happened_yet():
                        yield boper.NEXT_TIME
            boper.WHILE_TX_PENDING -- Run when there are no outbound messages
                queued for transmission.
        """
        if type(pname) is not str:
            raise TypeError("internal: handler name not a string: "+repr(pname))
        if pname in self.programme_handlers:
            raise KeyError("internal: handler already registered: \""+
                           pname+"\"")
        self.programme_handlers[pname] = phandler

    def handle_command(self, line):
        "Handle an input command 'line'"
        # Break the line into words
        words = []
        try:
            words = bmisc.supersplit(line, end_at = "#")
        except Exception as e:
            print("Unable to parse command line: "+str(e),
                  file=self.client.get_error_channel())
            if dbg.estk:
                print_exc(file=self.client.get_error_channel())
            return

        # ignore an empty command line
        if not words: return

        # the first word is the command, handle it
        if words[0] == "help":
            print("# Commands:\n"+
                  "#   echo ... -- write arbitrary text to output\n"++++
                  "#   exit -- exit bgpy_clnt entirely\n"+
                  "#   pause programme -- pause a running programme\n"+
                  "#   resume programme -- resume a paused programme\n"+
                  "#   run programme [args] -- start a canned programme\n"+
                  "#   stop programme -- stop a running programme\n",
                  file=self.client.get_error_channel())
        elif words[0] == "run":
            if len(words) < 2:
                print("Missing program name in 'run'",
                      file=self.client.get_error_channel())
                return
            pname = words[1]
            if pname not in self.programme_handlers:
                print("Unknown programme name '"+pname+"'.",
                      file=self.client.get_error_channel())
                return
            if pname in self.programme_iterators:
                print("Programme '"+pname+"' already running.",
                      file=self.client.get_error_channel())
                return
            it = self.programme_handlers[pname](self, self.client, words[2:])
            self.programme_iterators[pname] = it
            self.programme_iterator_times[pname] = 0
        elif words[0] == "pause":
            if len(words) != 2:
                print("Syntax error in 'pause'",
                      file=self.client.get_error_channel())
                return
            pname = words[1]
            if pname not in self.programme_handlers:
                print("Unknown programme name '"+pname+"'.",
                      file=self.client.get_error_channel())
                return
            if pname not in self.programme_iterators:
                print("Programme '"+pname+"' not running.",
                      file=self.client.get_error_channel())
                return
            self.programme_iterator_times[pname] = None
        elif words[0] == "resume":
            if len(words) != 2:
                print("Syntax error in 'resume'",
                      file=self.client.get_error_channel())
                return
            pname = words[1]
            if pname not in self.programme_handlers:
                print("Unknown programme name '"+pname+"'.",
                      file=self.client.get_error_channel())
                return
            if pname not in self.programme_iterators:
                print("Programme '"+pname+"' not running.",
                      file=self.client.get_error_channel())
                return
            self.programme_iterator_times[pname] = 0
        elif words[0] == "stop":
            if len(words) != 2:
                print("Syntax error in 'stop'",
                      file=self.client.get_error_channel())
                return
            pname = words[1]
            if pname not in self.programme_handlers:
                print("Unknown programme name "+repr(pname)+".",
                      file=self.client.get_error_channel())
                return
            if pname not in self.programme_iterators:
                print("Programme "+repr(pname)+" not running.",
                      file=self.client.get_error_channel())
                return
            del self.programme_iterators[pname]
            del self.programme_iterator_times[pname]
        elif words[0] == "echo":
            print(" ".join(words[1]),
                  file=self.client.get_error_channel())
        elif words[0] == "exit":
            if len(words) != 1:
                print("Syntax error in 'exit'",
                      file=self.client.get_error_channel())
            sys.exit(0)
        else:
            print("Unknown command '"+repr(word[0])+"'",
                  file=self.client.get_error_channel())
            return

    def invoke(self, now):
        """If any pending programme is to be run before the time 'now',
        run them; return the time in seconds before the next is to run, or
        None if there isn't any."""

        # This could be made more scalable with a priority queue, but
        # it's not really worth it for the intended use here.

        time_next = None
        for pname in self.programme_iterator_times:
            # find out what the recorded time to run the iterator is
            t = self.programme_iterator_times[pname]

            # shall we run it now?
            if t is None:
                # Paused indefinitely.
                run_it = False
            elif t is boper.NEXT_TIME:
                # This is "next time"
                run_it = True
            elif t is boper.WHILE_TX_PENDING:
                # Run if the outbound buffer is empty.
                run_it = (len(self.client.wrpsok.opnd) <= 0)
            elif t <= now:
                # Now it's time.
                run_it = True
            else:
                # It's not yet time.
                run_it = False

            # If so, go for it.
            if run_it:
                iterator = self.programme_iterators[pname]
                try:
                    t = next(iterator)
                    self.programme_iterator_times[pname] = t
                except StopIteration:
                    del self.programme_iterator_times[pname]
                    del self.programme_iterators[pname]

            # And account for the next time it's to run if any.
            if t is None:
                pass # waiting indefinitely
            elif t is boper.NEXT_TIME:
                pass # waiting until something else wakes us up
            elif t is boper.WHILE_TX_PENDING:
                # We're to wait for the outbound buffer to empty.
                if len(self.client.wrpsok.opnd) <= 0:
                    time_next = 0 # already happened
                else:
                    # Hasn't happened yet; we'll come back here by the time
                    # it does.
                    pass
            elif time_next is None or t < time_next:
                time_next = t # a time to wake up, before we were planning to

        if time_next is None:   return(None)
        else:                   return(max(0, time_next - now))

## ## ## Client class: one end of a BGP peering

def default_holdtime_expiry(clnt):
    """Handle hold time expiry the easy if lame way: Just print a message.
    The "correct" thing to do would be to end the connection at this
    point.  But for the present program, just printing a message and
    doing nothing else seems reasonable."""

    bmisc.stamprint("Hold time expired.")

class Client(object):
    """Main class of the bgpy_clnt application.  Holds state and settings
    and has ways to make things happen."""

    def __init__(self,
                 sok, local_as, router_id,
                 cmdfile = sys.stdin,
                 outfile = sys.stdout,
                 errfile = sys.stderr,
                 holdtime_sec = 60,
                 holdtime_expiry = default_holdtime_expiry
                 ):
        """Constructor.  Various parameters:
        Required:
            sok -- TCP socket connected to the peer
            local_as -- our local autonomous system (AS) number
            router_id -- router ID -- 32 bit integer or IPv4 address
                represented as int or 4 bytes
        Optional:
            cmdfile -- command input stream, default is stdin
            outfile -- regular output stream, default is stdin
            errfile -- error output stream, default is stdin
            holdtime_sec -- hold time to propose in seconds
            holdtime_expiry -- function (passed this Client object) to
                call when the negotiated hold time has expired
        """

        if type(holdtime_sec) is not int:
            raise TypeError("Hold time must be an integer")
        if holdtime_sec != 0 and holdtime_sec < 3:
            raise ValueError("Hold time must be 0 or >= 3 seconds")
        if holdtime_sec > 65535:
            raise ValueError("Hold time may be no more than 65535 seconds")

        self.env = brepr.BGPEnv()
        self.sok = sok
        self.wrpsok = boper.SocketWrap(sok, self.env)
        self.local_as = local_as
        if type(router_id) is int:
            if (router_id >> 32):
                raise ValueError("Router id must be 32 bits")
            ba = bytearray()
            bmisc.ba_put_be4(ba, router_id)
            router_id = ba
        router_id = bytes(router_id)
        if len(router_id) != 4:
            raise ValueError("Router id must be 32 bits")
        self.router_id = router_id
        self.cmdfile = cmdfile
        self.outfile = outfile
        self.errfile = errfile
        self.holdtime_sec = holdtime_sec
        self.open_sent = None           # BGP Open message we sent if any
        self.open_recv = None           # BGP Open message we received if any

        bmisc.stamprint("Connected.")

    def get_error_channel(self):
        return(self.errfile)

    def get_output_channel(self):
        return(self.outfile)

    # XXX much more in this class 'Client'

## ## ## Command line parameter handling

# name=value parameters we know about
equal_parms = bmisc.EqualParms()

equal_parms.add("local-as", "Local AS Number", bmisc.EqualParms_parse_i32)
equal_parms.parse("local-as=1") # default value
equal_parms.add_alias("las", "local-as")

equal_parms.add("router-id", "Router ID", bmisc.EqualParms_parse_i32_ip)
equal_parms.parse("router-id=0.0.0.1") # default value
equal_parms.add_alias("rtrid", "router-id")

equal_parms.add("tcp-hex", "Show TCP exchanges in hex",
                bmisc.EqualParms_parse_i32)
equal_parms.parse("tcp-hex=0") # default value

equal_parms.add("dbg", "enable the specified debug flag",
                None, lambda f: dbg.add(f))

## ## ## outer program skeleton

# command line parameters
def usage():
    print("USAGE: python3 bgpy_clnt.py [name=value...]" +
          " [\"@command...\"] peer-address",
          file=sys.stderr)
    print("Named parameters recognized:", file=sys.stderr)
    for n, d in equal_parms.describe():
        print("\t"+n+": "+d, file=sys.stderr)
    sys.exit(1)

if len(sys.argv) < 2:
    usage()

pre_commands = []

for a in sys.argv[1:-1]:
    # maybe it's a "@command..." to handle when ready
    if a[0] == "@":
        pre_commands.append(a[1:])
        continue

    # or else it's a name=value pair, match against equal_parms and parse
    try:
        equal_parms.parse(a)
    except Exception as e:
        print(str(e), file=sys.stderr)
        if dbg.estk:
            print_exc(file=sys.stderr)
        usage()

peer_addr = sys.argv[-1]

# open a connection

bmisc.stamprint("Started.")

sok = socket.socket(socket.AF_INET, socket.SOCK_STREAM,
                    socket.IPPROTO_TCP)
try:
    sok.connect((peer_addr, brepr.BGP_TCP_PORT))
        # XXX maybe add an optional parameter for remote TCP port
except Exception as e:
    print("Failed to connect to "+peer_addr+" port "+
          str(bmisc.BGP_TCP_PORT)+": "+str(e), file=sys.stderr)
    if dbg.estk:
        print_exc(file=sys.stderr)

c = Client(sok = sok,
           local_as = equal_parms["local-as"],
           router_id = equal_parms["router-id"])
if equal_parms["tcp-hex"]:
    # hex dump of all data sent/received over TCP
    tcp_hex_ipos = [0]
    tcp_hex_opos = [0]

    def tcp_hex_handler(wrpsok, rw, data):
        if len(data) == 0: return # nothing to do

        if rw is "r":   (posa, rws) = (tcp_hex_ipos, "tcp-rcv")
        else:           (posa, rws) = (tcp_hex_opos, "tcp-snd")

        bmisc.stamprint(rws+", "+str(len(data))+" bytes:")

        # byte values
        vs = list(map("{:02x}".format, data))

        # padding for alignment with posa[0]
        vs = ["  "] * (posa[0] & 15) + vs

        # display as lines, 16 bytes per line, with an address prefixed to it
        i = 0
        for i in range(0, len(vs), 16):
            print("{}.{:010x}: {}".format(rws, ((posa[0] & ~15) + i),
                                          " ".join(vs[i : (i + 16)])),
                  file=sys.stderr)
        posa[0] += len(data)

    c.env.data_cb = tcp_hex_handler

cmdi = Commanding(c)
cmdbuf = ""
register_programmes(cmdi)
for cmd in pre_commands:
    cmdi.handle_command(cmd)

# and then do... stuff: the main event loop

bmisc.tor.set()

while True:
    # Run any pending "programmes" and figure out how long until the next
    # scheduled event if any; this provides a timeout for select().
    timeo = cmdi.invoke(bmisc.tor.get())

    # build socket lists for select()
    rlist = []
    wlist = []
    xlist = []
    if c.wrpsok.want_recv(): rlist.append(c.sok)
    if c.wrpsok.want_send(): wlist.append(c.sok)

    # Add the command interface (stdin).  Windows won't like this since it's
    # not a socket.
    rlist.append(sys.stdin)

    if dbg.sokw:
        bmisc.stamprint("select" + repr((rlist, wlist, xlist, timeo)))

    (rlist, wlist, xlist) = select.select(rlist, wlist, xlist, timeo)

    bmisc.tor.set()

    t = bmisc.tor.get()

    if dbg.sokw:
        bmisc.stamprint("select => " + repr((rlist, wlist, xlist)))

    if c.sok in wlist:
        # send some of any pending messages
        c.wrpsok.able_send()
    if c.sok in rlist:
        # receive some messages
        if not c.wrpsok.able_recv():
            bmisc.stamprint("Connection was closed")
            break
    if sys.stdin in rlist:
        # read a command, or part of one
        cmdbuf += sys.stdin.read(512)
        while True:
            nl = cmdbuf.find("\n")
            if nl < 0: break        # no more commands
            try:
                cmdi.handle_command(cmdbuf[0:nl])
            except Exception as e:
                print("Command failure: "+str(e), file=sys.stderr)
                if dbg.estk:
                    print_exc(file=sys.stderr)
            line = cmdbuf[nl:]
    while True:
        try:
            msg = c.wrpsok.recv()
        except Exception as e:
            bmisc.stamprint("Recv err: " + repr(e))
            if dbg.estk:
                for line in format_exc().split("\n"):
                    if line is not "":
                        bmisc.stamprint("    " + line)
        if msg is None:
            break       # no more messages
        elif msg.type == brepr.msg_type.OPEN:
            # received an Open message -- keep track of it
            if c.open_recv is None: c.open_recv = msg

