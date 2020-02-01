# bgpy_oper.py - begun 11 May 2019
# Copyright (c) 2019 Jeremy Dilatush
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY JEREMY DILATUSH AND CONTRIBUTORS
# ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL JEREMY DILATUSH OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
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

    __slots__ = ["sok", "env", "ipnd", "opnd", "ista",
                 "ibroke", "obroke", "quiet"]
    def __init__(self, sok, env):
        self.sok = sok      # connected socket
        self.env = env      # brepr.BGPEnv used in parsing
        self.ipnd = bytes() # input pending: received but not parsed / returned
        self.opnd = bytes() # output pending: formatted but not send
        self.ista = False   # input status:
                            #       True -- there *may* be a message to parse
                            #       False -- there's no message to parse
        self.ibroke = False # set when connection is broken on inbound side
        self.obroke = False # set when connection is broken on outbound side
        self.quiet = False  # set to reduce output
    def send(self, msg):
        "Queue a BGPMessage for sending"
        if self.obroke:
            bmisc.stamprint("SocketWrap.send(): disabled because connection" +
                            " was closed.")
        self.opnd += msg.raw
        if not self.quiet:
            bmisc.stamprint("Send: " + str(msg))
        if dbg.sokw:
            bmisc.stamprint("SocketWrap.send(): " + repr(len(msg.raw)) +
                            " bytes added to queue, => " + repr(len(self.opnd)))
    def recv(self):
        "Return a received BGPMessage, or None if there is none"
        if not self.ista:
            # already know there isn't one, don't waste time checking
            if dbg.sokw:
                bmisc.stamprint("SocketWrap.recv(): None")
            return(None)
        if len(self.ipnd) < 19:
            # there isn't a full header
            if dbg.sokw:
                bmisc.stamprint("SocketWrap.recv(): not a full header yet")
            self.ista = False
            return(None)
        # read the message length field of the header
        ml = (self.ipnd[16] << 8) + self.ipnd[17]
        if len(self.ipnd) < ml:
            # there isn't a full message
            if dbg.sokw:
                bmisc.stamprint("SocketWrap.recv(): not a full message yet")
            self.ista = False
            return(None)
        # consume, parse, and return the message
        mr = self.ipnd[:ml]
        self.ipnd = self.ipnd[ml:]
        if dbg.sokw:
            bmisc.stamprint("SocketWrap.recv(): message, " +
                            repr(ml) + " bytes")
        msg = brepr.BGPMessage.parse(self.env, ParseCtx(mr))
        if not self.quiet:
            bmisc.stamprint("Recv: " + str(msg))
        return(msg)
    def want_recv(self):
        """Indicates whether there's any point to receiving anything; use when
        preparing lists for select()"""
        return(not self.ibroke)
    def want_send(self):
        """Indicates whether there's anything to send; use when preparing
        lists for select()"""
        return(len(self.opnd) > 0 and not self.obroke)
    def able_recv(self):
        """Called when select() indicates this socket can receive something.
        Returns True normally, False if socket closed."""
        if dbg.sokw:
            bmisc.stamprint("SocketWrap.able_recv() called")
        if self.ibroke:
            bmisc.stamprint("SocketWrap.able_recv() doing nothing: conn broken")
            return
        get = 512
        try:
            got = self.sok.recv(get)
        except BrokenPipeError:
            got = bytes()
        except ConnectionResetError:
            got = bytes()

        if len(got):
            self.ipnd += got        # we got something: buffer it
            self.ista = True        # and it *might* be a message
            if self.env.data_cb is not None:
                self.env.data_cb(self, "r", got)
        else:
            # Connection has been closed
            self.ibroke = True
            if dbg.sokw:
                bmisc.stamprint("connection closure detected on recv")
            return(False)
        return(True)
    def able_send(self):
        "Called when select() indicates this socket can send something"
        if dbg.sokw:
            bmisc.stamprint("SocketWrap.able_send() called")
        if self.obroke:
            bmisc.stamprint("SocketWrap.able_send() doing nothing: conn broken")
            return
        try:
            sent = self.sok.send(self.opnd)
        except BrokenPipeError:
            sent = 0
        except ConnectionResetError:
            sent = 0
        if sent > 0:
            # we sent something, remove it from the output buffer
            if self.env.data_cb is not None:
                self.env.data_cb(self, "w", self.opnd[:sent])
            self.opnd = self.opnd[sent:]
        else:
            self.obroke = True
            if dbg.sokw:
                bmisc.stamprint("connection closure detected on send")
    def set_quiet(self, q):
        "Enable/disable the quiet flag that reduces output"
        self.quiet = q

## ## ## special tokens

# NEXT_TIME -- Used in the Commanding class of bgpy_clnt.  A "programme"
# can yield it to indicate it should be run the next time through the
# event loop, no matter how long or short a time that is.
@bmisc.single_instance
class NEXT_TIME(object):
    def __init__(self): pass
    def __repr__(self): return("NEXT_TIME()")

# WHILE_TX_PENDING -- Used in the Commanding class of bgpy_clnt.  A
# "programme" can yield it to indicate it should be run as soon as
# all currently pending output messages have been sent
@bmisc.single_instance
class WHILE_TX_PENDING(object):
    def __init__(self): pass
    def __repr__(self): return("WHILE_TX_PENDING()")

# RIGHT_NOW -- Used in the Commanding class of bgpy_clnt.  A "programme"
# can yield it to indicate it should be run again right away, but only after
# going through the event loop again.
@bmisc.single_instance
class RIGHT_NOW(object):
    def __init__(self): pass
    def __repr__(self): return("RIGHT_NOW()")

