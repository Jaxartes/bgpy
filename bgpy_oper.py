# Jeremy Dilatush - All rights reserved.
# bgpy_oper.py - begun 11 May 2019
"""BGP protocol operations.  In a *real* BGP routing implementation this
would be huge, but for my current plans for "bgpy" it's not going to need
so much.

See also bgpy_repr.py which contains the on-wire data formats and
constants and such.
"""

## ## ## Top matter

from bgpy_misc import dbg
import bgpy_misc as bmisc
import bgpy_repr as brepr
from bgpy_misc import ConstantSet, ParseCtx
import sys, time

## ## ## Socket wrapper

class SocketWrap(object):
    """Wrap a TCP socket turning it into a means for sending
    and receiving BGP messages.  There are methods to aid integration
    with select() too.
    """

    __slots__ = ["sok", "env", "ipnd", "opnd", "ista"]
    def __init__(self, sok, env):
        self.sok = sok      # connected socket
        self.env = env      # brepr.BGPEnv used in parsing
        self.ipnd = bytes() # input pending: received but not parsed / returned
        self.opnd = bytes() # output pending: formatted but not send
        self.ista = False   # input status:
                            #       True -- there *may* be a message to parse
                            #       False -- there's no message to parse
    def send(self, msg):
        "Queue a BGPMessage for sending"
        self.opnd += msg.raw
        if dbg.sokw:
            bmisc.stamprint(sys.stderr, time.time(),
                            "SocketWrap.send(): " + repr(len(msg.raw)) +
                            " bytes added to queue, => " + repr(len(self.opnd)))
    def recv(self):
        "Return a received BGPMessage, or None if there is none"
        if not self.ista:
            # already know there isn't one, don't waste time checking
            if dbg.sokw:
                bmisc.stamprint(sys.stderr, time.time(),
                                "SocketWrap.recv(): None")
            return(None)
        if len(self.ipnd) < 19:
            # there isn't a full header
            if dbg.sokw:
                bmisc.stamprint(sys.stderr, time.time(),
                                "SocketWrap.recv(): not a full header yet")
            self.ista = False
            return(None)
        # read the message length field of the header
        ml = (self.ipnd[16] << 8) + self.ipnd[17]
        if len(self.ipnd) < ml:
            # there isn't a full message
            if dbg.sokw:
                bmisc.stamprint(sys.stderr, time.time(),
                                "SocketWrap.recv(): not a full message yet")
            self.ista = False
            return(None)
        # consume, parse, and return the message
        mr = self.ipnd[:ml]
        self.ipnd = self.ipnd[ml:]
        if dbg.sokw:
            bmisc.stamprint(sys.stderr, time.time(),
                            "SocketWrap.recv(): message, " +
                            repr(ml) + " bytes")
        return(brepr.BGPMessage.parse(self.env, ParseCtx(mr)))
    def want_recv(self):
        """Indicates whether there's any point to receiving anything; use when
        preparing lists for select()"""
        return(True)
    def want_send(self):
        """Indicates whether there's anything to send; use when preparing
        lists for select()"""
        return(len(self.opnd) > 0)
    def able_recv(self):
        """Called when select() indicates this socket can receive something.
        Returns True normally, False if socket closed."""
        if dbg.sokw:
            bmisc.stamprint(sys.stderr, time.time(),
                            "SocketWrap.able_recv() called")
        get = 8 # XXX change this to something bigger after testing
        got = self.sok.recv(get)
        if len(got):
            self.ipnd += got        # we got something: buffer it
            self.ista = True        # and it *might* be a message
            if self.env.data_cb is not None:
                self.env.data_cb(self, "r", got)
        else:
            # Connection has been closed
            return(False)
        return(True)
    def able_send(self):
        "Called when select() indicates this socket can send something"
        if dbg.sokw:
            bmisc.stamprint(sys.stderr, time.time(),
                            "SocketWrap.able_send() called")
        sent = self.sok.send(self.opnd)
        if sent > 0:
            # we sent something, remove it from the output buffer
            if self.env.data_cb is not None:
                self.env.data_cb(self, "w", self.opnd[:sent])
            self.opnd = self.opnd[sent:]
        else:
            # this is a problem; what do we do about it?
            raise Exception("XXX")

## ## ## special tokens

# NEXT_TIME -- Used in the Commanding class of bgpy_clnt.  A "programme"
# can yield it to indicate it should be run the next time through the
# event loop, no matter how long or short a time that is.
NEXT_TIME = object()

