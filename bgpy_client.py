# Jeremy Dilatush - All rights reserved.
# bgpy_client.py - begun 27 April 2019
"""This is the "skeleton" of the bgpy BGP implementation in Python.
It provides a limited BGP tester that can connect to a BGP peer, exchange
open and keepalive messages as required, and perform other operations
(chiefly running "canned programmes" that might send BGP routes) as
requested on stdin."""

## ## ## Top matter

import socket
import sys
import time
import bgpy_misc as bmisc
import bgpy_repr as brepr

## ## ## Command interface on stdin

class Commanding(object):
    """Command interface of bgpy_client.  Handle commands that are meant
    to come in on stdin.  Each command takes up a line. One command is "help".
    It documents the others."""

    def __init__(self, bgpy_client):
        "initialize the Commanding object"
        # programme_handlers maps the name of a programme to its handler; see
        # register_programme()
        # programme_iterators maps the name of a programme already started
        # to its iterator; see register_programme().
        # bgpy_client is the client object to which the commands apply,
        # which will in turn be passed to programme handlers etc.
        # programme_iterator_times indicates when each should run; 0 means
        # immediately; None means it's suspended
        self.programme_handlers = dict()
        self.programme_iterators = dict()
        self.programme_iterator_times = dict()
        self.bgpy_client = dict()

    def register_programme(self, pname, phandler):
        """Register a 'canned programme', with the given name, and a handler.
        The handlers is to be called with a list of argument strings, and
        generate an iterable.  That iterable, when next() is called on it,
        should do whatever's desired of the canned program, and yield
        one of the following:
            number -- time to wait until before doing next() again
            None -- wait for an explicit "resume" command
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
                  file=self.bgpy_client.get_error_channel())
            return

        # ignore an empty command line
        if not words: return

        # the first word is the command, handle it
        if words[0] == "help":
            print("# Commands:\n"+
                  "#   echo ... -- write arbitrary text to output\n"++++
                  "#   exit -- exit bgpy_client entirely\n"+
                  "#   pause programme -- pause a running programme\n"+
                  "#   resume programme -- resume a paused programme\n"+
                  "#   run programme [args] -- start a canned programme\n"+
                  "#   stop programme -- stop a running programme\n",
                  file=self.bgpy_client.get_error_channel())
        elif words[0] == "run":
            if len(words) < 2:
                print("Missing program name in 'run'",
                      file=self.bgpy_client.get_error_channel())
                return
            pname = words[1]
            if pname not in self.programme_handlers:
                print("Unknown programme name '"+pname+"'.",
                      file=self.bgpy_client.get_error_channel())
                return
            if pname in self.programme_iterators:
                print("Programme '"+pname+"' already running.",
                      file=self.bgpy_client.get_error_channel())
                return
            it = self.programme_handlers[pname](self.bgpy_client, words[2:])
            self.programme_iterators[pname] = it
            self.programme_iterator_times[pname] = 0
        elif words[0] == "pause":
            if len(words) != 2:
                print("Syntax error in 'pause'",
                      file=self.bgpy_client.get_error_channel())
                return
            pname = words[1]
            if pname not in self.programme_handlers:
                print("Unknown programme name '"+pname+"'.",
                      file=self.bgpy_client.get_error_channel())
                return
            if pname not in self.programme_iterators:
                print("Programme '"+pname+"' not running.",
                      file=self.bgpy_client.get_error_channel())
                return
            self.programme_iterators_times[pname] = None
        elif words[0] == "resume":
            if len(words) != 2:
                print("Syntax error in 'resume'",
                      file=self.bgpy_client.get_error_channel())
                return
            pname = words[1]
            if pname not in self.programme_handlers:
                print("Unknown programme name '"+pname+"'.",
                      file=self.bgpy_client.get_error_channel())
                return
            if pname not in self.programme_iterators:
                print("Programme '"+pname+"' not running.",
                      file=self.bgpy_client.get_error_channel())
                return
            self.programme_iterators_times[pname] = 0
        elif words[0] == "stop":
            if len(words) != 2:
                print("Syntax error in 'stop'",
                      file=self.bgpy_client.get_error_channel())
                return
            pname = words[1]
            if pname not in self.programme_handlers:
                print("Unknown programme name "+repr(pname)+".",
                      file=self.bgpy_client.get_error_channel())
                return
            if pname not in self.programme_iterators:
                print("Programme "+repr(pname)+" not running.",
                      file=self.bgpy_client.get_error_channel())
                return
            del self.programme_iterators[pname]
            del self.programme_iterator_times[pname]
        elif words[0] == "echo":
            print(" ".join(words[1]),
                  file=self.bgpy_client.get_error_channel())
        elif words[0] == "exit":
            if len(words) != 1:
                print("Syntax error in 'exit'",
                      file=self.bgpy_client.get_error_channel())
            sys.exit(0)
        else:
            print("Unknown command '"+repr(word[0])+"'",
                  file=self.bgpy_client.get_error_channel())
            return
    def invoke(self, now):
        """If any pending programme is to be run before the time 'now',
        run one; return the time in seconds before the next is to run."""

        # This could be made more scalable with a priority queue, but
        # it's not really worth it for the intended use here.

        time_next = None
        ran_one = False
        for pname in self.programme_iterator_times:
            t = self.programme_iterator_times[pname]
            if not ran_one and t is not None and t <= now:
                # Ok, run this one.
                iterator = self.programme_iterators[pname]
                try:
                    t = iterator.next()
                    self.programme_iterator_times[pname] = t
                except StopIteration:
                    del self.programme_iterator_times[pname]
                    del self.programme_iterators[pname]
            if t is not None and t < time_nxt:
                time_next = t

        return(time_next)

## ## ## Client class: one end of a BGP peering

def default_holdtime_expiry(clnt):
    """Handle hold time expiry the easy if lame way: Just print a message.
    The "correct" thing to do would be to end the connection at this
    point.  But for the present program, just printing a message and
    doing nothing else seems reasonable."""

    bmisc.stamprint(clnt.errfile, clnt.time, "Hold time expired.")

class Client(object):
    """Main class of the bgpy_client application.  Holds state and settings
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

        self.sok = sok
        self.router_id = router_id
        self.cmdfile = cmdfile
        self.outfile = outfile
        self.errfile = errfile
        self.holdtime_sec = holdtime_sec
        self.time = time.time()         # current time stamp of record

        bmisc.stamprint(self.errfile, self.time, "Connected.")

    def get_error_channel(self):
        return(self.errfile)

    def get_output_channel(self):
        return(self.outfile)

    # XXX much more

## ## ## outer program skeleton

# command line parameters
def usage():
    print("USAGE: python3 bgpy_client.py local-as router-id peer-address",
          file=sys.stderr)
    sys.exit(1)

if len(sys.argv) != 4:
    usage()

try:
    local_as = int(sys.argv[1])
    if local_as < 0 or local_as > 4294967295:
        raise Exception()
except:
    print("local AS number must be integer in 0-4294967295 range",
          file=sys.stderr)
    usage()

try:
    router_id = int(sys.argv[2])
    if router_id < 0 or router_id > 4294967295:
        raise Exception()
except:
    try:
        router_id_bytes = socket.inet_aton(sys.argv[2])
        router_id = 0
        for router_id_byte in router_id_bytes:
            router_id = (router_id << 8) + router_id_byte
    except:
        print("router ID must be either an IPv4 address in dotted quad\n"+
              "format, or an integer in 0-4294967295 range.", file=sys.stderr)
        usage()
    # Apparently, socket.inet_aton() tolerates some things I wouldn't
    # expect it to.  Ah well.

peer_addr = sys.argv[3]

# open a connection

bmisc.stamprint(sys.stderr, time.time(), "Started.")

sok = socket.socket(socket.AF_INET, socket.SOCK_STREAM,
                    socket.IPPROTO_TCP)
try:
    sok.connect((peer_addr, brepr.BGP_TCP_PORT))
except Exception as e:
    print("Failed to connect to "+peer_addr+" port "+
          str(bmisc.BGP_TCP_PORT)+": "+str(e), file=sys.stderr)

bmisc.stamprint(sys.stderr, time.time(), "Connected.")
c = Client(sok = sok, local_as = local_as, router_id = router_id)

# and then do... stuff

# XXX do event loop
