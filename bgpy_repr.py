# Jeremy Dilatush - All rights reserved.
# bgpy_repr.py - begun 28 April 2019
"""Representation of packets and parts of packets in the BGP protocol.
This isn't the whole protocol implementation, just the decoding/encoding
parts.  It has a bunch of classes representing things like messages,
attributes, AS path, etc; these can be read and written in the binary
form used by the protocol and also in a printable text form.

Also contains constants and data like that.  Generally, static aspects
of the protocol.
"""

## ## ## Top matter

import bgpy_misc as bmisc
from bgpy_misc import ConstantSet, ParseCtx
import sys

## ## ## Constants

# the well-known TCP port number assigned to BGP
BGP_TCP_PORT = 179

# BGP Message Types -- see RFC 4271, also
# https://www.iana.org/assignments/bgp-parameters/bgp-parameters-1.csv
msg_type = ConstantSet(
    OPEN            = 1,    # RFC 4271
    UPDATE          = 2,    # RFC 4271
    NOTIFICATION    = 3,    # RFC 4271
    KEEPALIVE       = 4,    # RFC 4271
    ROUTE_REFRESH   = 5,    # RFC 2918
)

# BGP version
bgp_ver = ConstantSet(
    FOUR            = 4,    # BGP version 4
)

# BGP OPEN Optional Parameter Types -- see
# https://www.iana.org/assignments/bgp-parameters/bgp-parameters-11.csv
bgp_parms = ConstantSet(
    Authentication      = 1,    # (deprecated) RFC 4271, RFC 5492
    Capabilities        = 2,    # RFC 5492
)

# BGP Path Attributes -- see RFC 4271, others, also
# https://www.iana.org/assignments/bgp-parameters/bgp-parameters-2.csv
attr_code = ConstantSet(
    ORIGIN              = 1,    # RFC 4271
    AS_PATH             = 2,    # RFC 4271
    NEXT_HOP            = 3,    # RFC 4271
    MULTI_EXIT_DISC     = 4,    # RFC 4271
    LOCAL_PREF          = 5,    # RFC 4271
    ATOMIC_AGGREGATE    = 6,    # RFC 4271
    AGGREGATOR          = 7,    # RFC 4271
    COMMUNITY           = 8,    # RFC 1997
    ORIGINATOR_ID       = 9,    # RFC 4456
    CLUSTER_LIST        = 10,   # RFC 4456
    MP_REACH_NLRI       = 14,   # RFC 4760
    MP_UNREACH_NLRI     = 15,   # RFC 4760
    EXTENDED_COMMUNITIES = 16,  # RFC 4360
    AS4_PATH            = 17,   # RFC 6793
    AS4_AGGREGATOR      = 18,   # RFC 6793
    PMSI_TUNNEL         = 22,   # RFC 6514
    Tunnel_Encapsulation = 23,  # RFC 5512
    Traffic_Engineering = 24,   # RFC 5543
    IPv6_Address_Specific_Extended_Community = 25, # RFC 5701
    AIGP                = 26,   # RFC 7311
    PE_Distinguisher_Labels = 27, # RFC 6514
    BGP_LS              = 29,   # RFC 7752
    LARGE_COMMUNITY     = 32,   # RFC 8092
    BGPsec_Path         = 33,   # RFC 8205
    ATTR_SET            = 128,  # RFC 6368
)

# BGP Error Codes -- see RFC 4271, also
# https://www.iana.org/assignments/bgp-parameters/bgp-parameters-3.csv
err_code = ConstantSet(
    ( "msghdr", "Message Header Error",         1 ), # RFC 4271
    ( "opnmsg", "OPEN Message Error",           2 ), # RFC 4271
    ( "updmsg", "UPDATE Message Error",         3 ), # RFC 4271
    ( "hldexp", "Hold Timer Expired",           4 ), # RFC 4271
    ( "fsm",    "Finite State Machine Error",   5 ), # RFC 4271
    ( "cease",  "Cease",                        6 ), # RFC 4271
    ( "rfrmsg", "ROUTE-REFRESH Message Error",  7 ), # RFC 7313
)

# BGP Error Subcodes -- see RFC 4271, also
# https://www.iana.org/assignments/bgp-parameters/bgp-parameters-5.csv
#   (Message Header Error subcodes)
# https://www.iana.org/assignments/bgp-parameters/bgp-parameters-6.csv
#   (OPEN Message Error subcodes)
# https://www.iana.org/assignments/bgp-parameters/bgp-parameters-7.csv
#   (UPDATE Message Error subcodes)
# https://www.iana.org/assignments/bgp-parameters/bgp-finite-state-machine-error-subcodes.csv
#   (BGP Finite State Machine Error Subcodes)
# https://www.iana.org/assignments/bgp-parameters/bgp-parameters-8.csv
#   (BGP Cease NOTIFICATION message subcodes)
# https://www.iana.org/assignments/bgp-parameters/route-refresh-error-subcodes.csv
#   (BGP ROUTE-REFRESH Message Error subcodes)
err_sub_msghdr = ConstantSet(
    ( "unspec", "Unspecific",                   0 ),    # RFC Errata 4493
    ( "notsyn", "Connection Not Synchronized",  1 ),    # RFC 4271
    ( "msglen", "Bad Message Length",           2 ),    # RFC 4271
    ( "msgtyp", "Bad Message Type",             3 ),    # RFC 4271
)
err_sub_opnmsg = ConstantSet(
    ( "unspec", "Unspecific",                   0 ),    # RFC Errata 4493
    ( "vernum", "Unsupported Version Number",   1 ),    # RFC 4271
    ( "peeras", "Bad Peer AS",                  2 ),    # RFC 4271
    ( "rtrid",  "Bad BGP Identifier",           3 ),    # RFC 4271
    ( "option", "Unsupported Optional Parameter", 4 ),  # RFC 4271
    ( "hldtim", "Unacceptable Hold Time",       6 ),    # RFC 4271
    ( "capab",  "Unsupported Capability",       7 ),    # RFC 5492
)
err_sub_updmsg = ConstantSet(
    ( "unspec", "Unspecific",                   0 ),    # RFC Errata 4493
    ( "attlst", "Malformed Attribute List",     1 ),    # RFC 4271
    ( "unkwel", "Unrecognized Well-known Attribute", 2 ), # RFC 4271
    ( "miswel", "Missing Well-known Attribute", 3 ),    # RFC 4271
    ( "aflags", "Attribute Flags Error",        4 ),    # RFC 4271
    ( "attlen", "Attribute Length Error",       5 ),    # RFC 4271
    ( "origin", "Invalid ORIGIN Attribute",     6 ),    # RFC 4271
    ( "nxthop", "Invalid NEXT_HOP Attribute",   8 ),    # RFC 4271
    ( "optatt", "Optional Attribute Error",     9 ),    # RFC 4271
    ( "netwrk", "Invalid Network Field",        10 ),   # RFC 4271
    ( "aspath", "Malformed AS_PATH",            11 ),   # RFC 4271
)
# there are no subcodes for "Hold Timer Expired"
err_sub_fsm = ConstantSet(
    ( "unspec", "Unspecified Error", 0 ), # RFC 6608
    ( "opsent", "Receive Unexpected Message in OpenSent State", 1 ), # RFC 6608
    ( "opconf", "Receive Unexpected Message in OpenConfirm State", 2 ), # RFC 6608
    ( "establ", "Receive Unexpected Message in Established State", 3 ), # RFC 6608
)
err_sub_cease = ConstantSet(
    ( "maxpfx", "Maximum Number of Prefixes Reached", 1 ), # RFC 4486
    ( "adshut", "Administrative Shutdown",      2 ), # RFC 4486 & RFC8203
    ( "config", "Peer De-configured",           3 ), # RFC 4486
    ( "adrset", "Administrative Reset",         4 ), # RFC 4486 & RFC8203
    ( "reject", "Connection Rejected",          5 ), # RFC 4486
    ( "config", "Other Configuration Change",   6 ), # RFC 4486
    ( "collis", "Connection Collision Resolution", 7 ), # RFC 4486
    ( "resour", "Out of Resources",             8 ), # RFC 4486
    ( "reset",  "Hard Reset",                   9 ), # RFC 8538
)
err_sub_rfrmsg = ConstantSet(
    ( "reserv", "Reserved",                     0 ), # RFC 7313
    ( "msglen", "Invalid Message Length",       1 ), # RFC 7313
)

# The all-ones marker defined in RFC 4271 4.1
BGP_marker = bytes(b"\xff" * 16)

## ## ## BGP Configuration-like State

class BGPEnv(object):
    """A handful of settings that impact how BGP handles things:
        as4 -- whether 4 byte AS numbers are in use
        data_cb -- callback to run when data is received or sent
    """
    def __init__(self, cpy = None):
        if cpy is None:
            self.as4 = False
            self.data_cb = None
        else:
            self.as4 = cpy.as4
            self.data_cb = cpy.data_cb

## ## ## Representing "things" in BGP

class BGPThing(object):
    """Base class for things that are transmitted/received in the BGP
    protocol.  There will be subclasses for BGP messages, attributes, etc.

    For every subclass you can:
        query the kind of thing it is:
            thing.bgp_thing_type()
            will return a class, which might not actually equal type(thing)
            but should be sort of the highest meaningful applicable entry in the
            subclass heirarchy
        query the kind of thing it is, in human readable string form:
            thing.bgp_thing_type_str()
            will be like thing.bgp_thing_type() but give a short string
        query the raw binary representation of the thing:
            thing.raw; type bytes
        get a string representation of the thing:
            str(thing)
            should be reasonably precise and detailed but not too long
            winded; both human and machine readable, more or less
    """
    __slots__ = ["raw"]
    def __init__(self, env, raw):
        """Parse from a specified BGPEnv and raw binary data."""
        self.raw = bytes(raw)
    def bgp_thing_type(self): return(BGPThing)
    def bgp_thing_type_str(self): return("?")
    def __str__(self):
        """Default string representation for a BGPThing: kind(raw=raw)"""
        hx = ".".join(map("{:02x}".format, self.raw))
        return(self.bgp_thing_type_str() + "(raw=" + hx + ")")

## ## ## Addresses

class IPv4Prefix(BGPThing):
    """An IPv4 address range as found in BGP update messages.
    Contains up to 4 bytes of address, and a masklength (number of bits)."""
    __slots__ = ["pfx", "ml"]
    def __init__(self, *args):
        """Initialize either from raw byte data or a prefix & masklen."""
        if len(args) == 1:
            # raw binary data; parse it
            BGPThing.__init__(self, args[0])
            pc = ParseCtx(self.raw)
            if len(pc) < 1:
                raise Exception("too short to be real")
            self.ml = pc.get_byte()
            nbytes = (self.ml + 7) >> 3
            if len(pc) != nbytes:
                raise Exception("IPv4Prefix bad length, " +
                                str(len(pc)) + " bytes to represent " +
                                str(self.ml) + " bits.")
            self.pfx = bytes(pc)
        elif len(args) == 2:
            # prefix & masklen; store it
            self.pfx = bytes(args[0])
            self.ml = int(args[1])
            if self.ml < 0 or self.ml > 32:
                raise Exception("mask length "+ str(self.ml) + " out of range")
            # sanitize the length
            nbytes = (self.ml + 7) >> 3
            if len(self.pfx) < nbytes:
                self.pfx += bytes(nbytes - len(self.pfx))
            elif len(self.pfx) > nbytes:
                self.pfx = self.pfx[0:nbytes]
            # build raw format
            ba = bytearray()
            ba.append(self.ml)
            ba += self.pfx
            BGPThing.__init__(self, ParseCtx(ba))
        else:
            raise Exception("IPv4Prefix() bad parameters")
    def bgp_thing_type(self): return(IPv4Prefix)
    def bgp_thing_type_str(self): return("v4pfx")
    def __str__(self):
        octets = list(self.pfx)
        while len(octets) < 4: octets.append(0)
        return(".".join(map(str, octets)) + "/" + str(self.ml))

## ## ## BGP Messages

class BGPMessage(BGPThing):
    """A BGP message -- see RFC 4271 4.1."""
    __slots__ = ["type", "payload"]
    def __init__(self, env, *args):
        """Parse from a specified BGPEnv and additional information that
        might be just raw binary data (to parse) or type and payload
        (itself raw)"""
        if len(args) == 1:
            # raw binary data; parse it
            BGPThing.__init__(self, args[0])
            pc = ParseCtx(self.raw)
            if len(pc) < 19:
                # header takes up 19 bytes
                raise Exception("BGPMessage too short for complete header")
            m = pc.get_bytes(16)
            if m != BGP_marker:
                # RFC 4271 4.1 says this must be 16 bytes of all-ones
                hx = " ".join(map("{:02x}".format, m))
                raise Exception("BGPMessage bad marker field ("+hx+")")
            l = pc.get_be2()
            if l < 19:
                # restriction specified in RFC 4271 4.1
                raise Exception("BGPMessage too short for complete header")
            if l > 4096:
                # restriction specified in RFC 4271 4.1
                raise Exception("BGPMessage too long")
            if l != len(self.raw):
                raise Exception("BGPMessage length mismatch (internal)")
            self.type = pc.get_byte()
            self.payload = pc
        elif len(args) == 2 and type(args[0]) is int:
            # type and payload; build message out of it
            self.type = args[0]
            self.payload = args[1]
            l = len(self.payload) + 19 # length field
            if l > 4096:
                # restriction specified in RFC 4271 4.1
                raise Exception("BGPMessage too long")
            if self.type < 0 or self.type > 255:
                # it has to fit in a byte
                raise Exception("BGPMessage type out of range (internal)")
            ba = bytearray()
            bmisc.ba_put_be2(ba, l)
            ba.append(self.type)
            ba.append(self.payload)
            BGPThing.__init__(self, ba)
        else:
            raise Exception("BGPMessage() bad parameters")
    def bgp_thing_type(self): return(BGPMessage)
    def bgp_thing_type_str(self): return("msg")
    def __str__(self):
        hx = ".".join(map("{:02x}".format, self.payload))
        return("msg(type=" + msg_type.value2name(self.type) +
               ", pld=" + hx + ")")

class BGPOpen(BGPMessage):
    """A BGP open message -- see RFC 4271 4.2."""
    __slots__ = ["version", "my_as", "hold_time",
                 "peer_id", "parms"]
    def __init__(self, env, *args):
        """Parse a BGP Open."""
        if len(args) == 1 and type(args[0]) is BGPMessage:
            # A BGPMessage; further parse its payload field.
            # Intentionally doesn't check its type.
            msg = args[0]
            basic_len = 10

            # Fields in BGPThing and BGPMessage
            BGPThing.__init__(self, msg.raw)
            self.type = msg.type
            self.payload = msg.payload

            # Fixed-length parts of the payload
            pc = ParseCtx(self.payload)
            if len(pc) < basic_len:
                raise Exception("BGPOpen too short for complete message")
            self.version = pc.get_byte()
            self.my_as = pc.get_be2()
            self.hold_time = pc.get_be2()
            self.peer_id = pc.get_bytes(4)

            # Variable-length parts of the payload: "Optional Parameters"
            parmslen = pc.get_byte()
            if parmslen != len(pc):
                raise Exception("BGPOpen optional parameters length mismatch")
            self.parms = []
            while len(pc):
                if len(pc) < 2:
                    raise Exception("Truncated option in BGPOpen")
                pt = pc.get_byte()
                pl = pc.get_byte()
                if len(pc) < pl:
                    raise Exception("Truncated option in BGPOpen")
                self.parms.append(BGPParameter(type=pt,
                                               value=pc.get_bytes(pl)))
        elif len(args) == 5:
            # By fields (version, my_as, hold_time, peer_id, parms).
            # Given that, format the raw stuff.
            (self.version, self.my_as, self.hold_time, self.peer_id,
             self.parms) = args
            ba = bytearray()
            ba.append(self.version)
            bmisc.ba_put_be2(ba, self.my_as)
            bmisc.ba_put_be2(ba, self.hold_time)
            ba.append(self.peer_id[0])
            ba.append(self.peer_id[0])
            ba.append(self.peer_id[0])
            ba.append(self.peer_id[0])
            pl = 0
            for parm in self.parms: pl += len(parm.raw)
            if pl > 255:
                raise Error("Optional parameters too long")
            ba.append(pl)
            for parm in self.parms: ba += bytes(parm.raw)
            BGPThing.__init__(self, ba)
        else:
            raise Exception("BGPOpen() bad parameters")
    def __str__(self):
        return("msg(type=" + msg_type.value2name(self.type) +
               ", version=" + str(self.version) +
               ", my_as=" + str(self.my_as) +
               ", hold_time=" + str(self.hold_time) +
               ", peer_id=" + (".".join(map(str, self.peer_id))) +")")

class BGPUpdate(BGPMessage):
    """A BGP update message -- see RFC 4271 4.3."""
    __slots__ = ["withdrawn", "attrs", "nlri"]
    def __init__(self, env, *args):
        """Parse a BGP Update."""
        if len(args) == 1 and type(args[0]) is BGPMessage:
            # A BGPMessage; further parse its payload field.
            # Intentionally doesn't check its type.
            msg = args[0]

            # Fields in BGPThing and BGPMessage
            BGPThing.__init__(self, msg.raw)
            self.type = msg.type
            self.payload = msg.payload

            # The parts of the payload; first part, withdrawn routes
            pc = ParseCtx(self.payload)
            if len(pc) < 2:
                raise Exception("BGPUpdate bad length"+
                                " (withdrawn length part truncated)")
            withlen = pc.get_be2()
            if len(pc) < withlen:
                raise Exception("BGPUpdate bad length"+
                                " (withdrawn part truncated)")
            wpc = pc.get_bytes(withlen)
            self.withdrawn = BGPUpdate.parse_routes(env, "withdrawn part", wpc)

            # Next part, path attributes
            if len(pc) < 2:
                raise Exception("BGPUpdate bad length"+
                                " (attribute length part truncated)")
            attlen = pc.get_be2()
            if len(pc) < attlen:
                raise Exception("BGPUpdate bad length"+
                                " (attribute part truncated)")
            apc = pc.get_bytes(attlen)
            self.attrs = BGPUpdate.parse_attrs(env, apc)

            # Next part, Network Layer Reachability Information (NLRI)
            # taking up the rest of the message.
            self.nlri = BGPUpdate.parse_routes(env, "nlri part", pc)
        elif len(args) == 3:
            # By fields (withdrawn, attrs, nlri).  Given that, format
            # the raw stuff.
            (self.withdrawn, self.attrs, self.nlri) = args
            ba = bytearray()
            baw = bytearray()
            BGPUpdate.format_routes(env, baw, self.withdrawn)
            if len(baw) > 65535:
                raise Exception("BGPUpdate too many withdrawn routes to fit")
            bmisc.ba_put_be2(ba, len(baw))
            ba += baw
            baa = bytearray()
            BGPUpdate.format_attrs(env, baa, self.attrs)
            bmisc.ba_put_be2(ba, len(baa))
            ba += baa
            ban = bytearray()
            BGPUpdate.format_routes(env, ban, self.nlri)
            if len(ban) > 65535:
                raise Exception("BGPUpdate too many advertised routes to fit")
            bmisc.ba_put_be2(ba, len(ban))
            ba += ban
            BGPThing.__init__(self, ba)
        else:
            raise Exception("BGPUpdate() bad parameters")
    def __str__(self):
        return("msg(type=" + msg_type.value2name(self.type) +
                ", wd=["+
                (", ".join(map(str, self.withdrawn)))+
                "], at=["+
                (", ".join(map(str, self.attrs)))+
                "], nlri=["+
                (", ".join(map(str, self.nlri)))+
                "])")
    @staticmethod
    def parse_routes(env, inwhat, pc):
        """Parse a collection of routes into a list, from the "Withdrawn Routes"
        and "Network Layer Reachability Information" fields of the Update
        message.  Returns a list of what it found."""
        res = []
        while len(pc):
            # length of the prefix in bits; it's padded to bytes
            nbits = pc.get_byte()
            if nbits > 32:
                raise Exception("Impossible mask length > 32: "+str(nbits))
            # see about getting that value out
            nbytes = (ml + 7) >> 3
            if len(pc) < nbytes:
                raise Exception("Truncated address in " + inwhat +
                                " in BGPUpdate")
            bs = list(pc.get_bytes(nbytes))
            # mask out padding bits in the last byte, if any
            if nbits & 7:
                bs[-1] &= 254 << (7 - (nbits & 7))
            # and record that in 'res'
            res.append(IPv4Prefix(bytes(bs), nbits))
        return(res):
    @staticmethod
    def format_routes(env, ba, rtes):
        """Format a collection of routes rtes into a bytearray ba."""
        for rte in rtes:
            ba += rte.raw
    @staticmethod
    def parse_attrs(env, pc):
        """Parse a collection of attributes into a list, from the
        "Path Attributes" field of the Update message."""
        XXX
    @staticmethod
    def format_attrs(env, ba, attrs):
        """Format a collection of attributes attrs into a bytearray ba."""
        XXX

class BGPKeepalive(BGPMessage):
    """A BGP keepalive message -- see RFC 4271 4.4."""
    pass # XXX implement for real

class BGPNotification(BGPMessage):
    """A BGP notification message -- see RFC 4271 4.5."""
    pass # XXX implement for real

class BGPRouteRefreshMsg(BGPMessage):
    """A BGP route refresh message -- see RFC 2918 3."""
    pass # XXX implement for real

## ## ## BGP Parameters (like capabilities)

class BGPParameter(BGPThing):
    """A BGP optional parameter as found in the open message --
    see RFC 4271 4.2."""
    pass # XXX implement for real

