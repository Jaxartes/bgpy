# bgpy_repr.py - begun 28 April 2019
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

# BGP Path Attribute flags -- see RFC 4271.
attr_flag = ConstantSet(
    Optional            = 0x80, # RFC 4271 4.3 - 1 = attribute is optional
                                #                0 = attribute is well-known
    Transitive          = 0x40, # RFC 4271 4.3 - 1 = attribute is transitive
                                #                0 = attribute is non-transitive
    Partial             = 0x20, # RFC 4271 4.3 - 1 = information is partial
                                #                0 = information is complete
    Extended_Length     = 0x10, # RFC 4271 4.3 - 1 = two byte length
                                #                0 = one byte length
)

# Values of the BGP "ORIGIN" attribute defined in RFC 4271 4.3.
origin_code = ConstantSet(
    IGP                     = 0,
    EGP                     = 1,
    INCOMPLETE              = 2,
)

# BGP AS path segment types defined in RFC 4271 4.3 and RFC 5065 3.
path_seg_type = ConstantSet(
    AS_SET                  = 1, # RFC 4271 4.3
    AS_SEQUENCE             = 2, # RFC 4271 4.3
    AS_CONFED_SEQUENCE      = 3, # RFC 5065 3
    AS_CONFED_SET           = 4, # RFC 5065 3
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

# address family numbers, used in some places in BGP as "AFI"
# See https://www.iana.org/assignments/address-family-numbers/address-family-numbers-2.csv
afis = ConstantSet(
    ( "IP", "IP (IP version 4)", 1 ),
    ( "IP6", "IP6 (IP version 6)", 2 ),
    ( "NSAP", "NSAP", 3 ),
    ( "HDLC", "HDLC (8-bit multidrop)", 4 ),
    ( "BBN_1822", "BBN 1822", 5 ),
    ( "802", "802 (includes all 802 media plus Ethernet \"canonical format\")", 6 ),
    ( "E_163", "E.163", 7 ),
    ( "E_164_SMDS", "E.164 (SMDS, Frame Relay, ATM)", 8 ),
    ( "F_69", "F.69 (Telex)", 9 ),
    ( "X_121", "X.121 (X.25, Frame Relay)", 10 ),
    ( "IPX", "IPX", 11 ),
    ( "Appletalk", "Appletalk", 12 ),
    ( "Decnet_IV", "Decnet IV", 13 ),
    ( "Banyan_Vines", "Banyan Vines", 14 ),
    ( "E_164_NSAP", "E.164 with NSAP format subaddress", 15 ), # [ATM Forum UNI 3.1. October 1995.][Andy_Malis]
    ( "DNS", "DNS (Domain Name System)", 16 ),
    ( "Distinguished_Name", "Distinguished Name", 17 ), # [Charles_Lynn]
    ( "AS_Number", "AS Number", 18 ), # [Charles_Lynn]
    ( "XTP_IPv4", "XTP over IP version 4", 19 ), # [Mike_Saul]
    ( "XTP_IPv6", "XTP over IP version 6", 20 ), # [Mike_Saul]
    ( "XTP_native", "XTP native mode XTP", 21 ), # [Mike_Saul]
    ( "Fibre_Channel_Port", "Fibre Channel World-Wide Port Name", 22 ), # [Mark_Bakke]
    ( "Fibre_Channel_Node", "Fibre Channel World-Wide Node Name", 23 ), # [Mark_Bakke]
    ( "GWID", "GWID", 24 ), # [Subra_Hegde]
    ( "L2VPN", "AFI for L2VPN information", 25 ), # [RFC4761][RFC6074]
    ( "MPLS_TP_Section", "MPLS-TP Section Endpoint Identifier", 26 ), # [RFC7212]
    ( "MPLS_TP_LSP", "MPLS-TP LSP Endpoint Identifier", 27 ), # [RFC7212]
    ( "MPLS-TP_Pseudowire", "MPLS-TP Pseudowire Endpoint Identifier", 28 ), # [RFC7212]
    ( "MT_IP", "MT IP: Multi-Topology IP version 4", 29 ), # [RFC7307]
    ( "MT_IPv6", "MT IPv6: Multi-Topology IP version 6", 30 ), # [RFC7307]
)

# Subsequent Address Family Identifier (SAFI) values
# See RFC 4760 and:
# https://www.iana.org/assignments/safi-namespace/safi-namespace-2.csv
safis = ConstantSet(
    ( "unicast", "Network Layer Reachability Information used for unicast forwarding", 1 ), # [RFC4760]
    ( "multicast", "Network Layer Reachability Information used for multicast forwarding", 2 ), # [RFC4760]
    ( "MPLS", "Network Layer Reachability Information (NLRI) with MPLS Labels", 4 ), # [RFC8277]
    ( "MCAST_VPN", "MCAST-VPN", 5 ), # [RFC6514]
    ( "Pseudowires", "Network Layer Reachability Information used for Dynamic Placement of Multi-Segment Pseudowires", 6 ), # [RFC7267]
    ( "Encapsulation", "Encapsulation SAFI", 7 ), # [RFC5512]
    ( "MCAST_VPLS", "MCAST-VPLS", 8 ), # [RFC7117]
    ( "Tunnel", "Tunnel SAFI", 64 ), # [Gargi_Nalawade][draft-nalawade-kapoor-tunnel-safi-01]
    ( "VPLS", "Virtual Private LAN Service (VPLS)", 65 ), # [RFC4761][RFC6074]
    ( "MDT", "BGP MDT SAFI", 66 ), # [RFC6037]
    ( "4over6", "BGP 4over6 SAFI", 67 ), # [RFC5747]
    ( "6over4", "BGP 6over4 SAFI", 68 ), # [Yong_Cui]
    ( "L1VPN_auto_disc", "Layer-1 VPN auto-discovery information", 69 ), # [RFC5195]
    ( "EVPNs", "BGP EVPNs", 70 ), # [RFC7432]
    ( "LS", "BGP-LS", 71 ), # [RFC7752]
    ( "LS_VPN", "BGP-LS-VPN", 72 ), # [RFC7752]
    ( "MPLS_VPN", "MPLS-labeled VPN address", 128 ), # [RFC4364][RFC8277]
    ( "MPLS_VPN_Multicast", "Multicast for BGP/MPLS IP Virtual Private Networks (VPNs)", 129 ), # [RFC6513][RFC6514]
    ( "RT_constr", "Route Target constrains", 132 ), # [RFC4684]
    ( "IPv4_diss_flow_spec", "IPv4 dissemination of flow specification rules", 133 ), # [RFC5575]
    ( "VPNv4_diss_flow_spec", "VPNv4 dissemination of flow specification rules", 134 ), # [RFC5575]
)

# BGP capability codes; see RFC 5492 and
# https://www.iana.org/assignments/capability-codes/capability-codes-2.csv
capabilities = ConstantSet(
    ( "mp", "Multiprotocol Extensions for BGP-4", 1 ), # RFC2858
    ( "refr", "Route Refresh Capability for BGP-4", 2 ), # RFC2918
    ( "filt", "Outbound Route Filtering Capability", 3 ), # RFC5291
    ( "multr", "Multiple routes to a destination capability (deprecated)", 4 ), # RFC8277
    ( "extnh", "Extended Next Hop Encoding", 5 ), # RFC5549
    ( "extmsg", "BGP Extended Message", 6 ), # RFC8654
    ( "bgpsec", "BGPsec Capability", 7 ), # RFC8205
    ( "multl", "Multiple Labels Capability", 8 ), # RFC8277
    ( "gr", "Graceful Restart Capability", 64 ), # RFC4724
    ( "as4", "Support for 4-octet AS number capability", 65 ), # RFC6793
    ( "add_path", "ADD-PATH Capability", 69 ), # RFC7911
    ( "enh_refr", "Enhanced Route Refresh Capability", 70 ), # RFC7313
)

# The all-ones marker defined in RFC 4271 4.1
BGP_marker = bytes(b"\xff" * 16)

# "AS_TRANS", defined in RFC 6793 to be substituted for a 4-byte AS number
# where only a 2-byte AS number fits.
AS_TRANS = 23456

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
    def with_as4(self, as4):
        """Copy this BGPEnv but with different 'as4' value"""
        cpy = BGPEnv(self)
        cpy.as4 = bool(as4)
        return(cpy)

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
    def __init__(self, env, *args):
        """Initialize either from raw byte data or a prefix & masklen."""

        if len(args) == 1 and type(args[0]) is str:
            # string; parse it
            pfx_ml = args[0].split("/", 1)
            if len(pfx_ml) < 2:
                pfx_ml.append("32")
            pfx = bmisc.parse_ipv4(pfx_ml[0])
            ml = int(pfx_ml[1])
            self.__init__(env, pfx, ml)
        elif len(args) == 1:
            # raw binary data; parse it
            BGPThing.__init__(self, env, args[0])
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
            if bmisc.mask_check(self.pfx, self.ml)[1]:
                a = ".".join(map(str, self.pfx)) + "/" + str(self.ml)
                raise Exception(a + " has host bits set")
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
            BGPThing.__init__(self, env, ParseCtx(bytes(ba)))
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
            BGPThing.__init__(self, env, args[0])
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
            ba += BGP_marker
            bmisc.ba_put_be2(ba, l)
            ba.append(self.type)
            ba += self.payload
            BGPThing.__init__(self, env, ba)
        else:
            raise Exception("BGPMessage() bad parameters")
    def bgp_thing_type(self): return(BGPMessage)
    def bgp_thing_type_str(self): return("msg")
    def __str__(self):
        hx = ".".join(map("{:02x}".format, self.payload))
        return("msg(type=" + msg_type.value2name(self.type) +
               ", pld=" + hx + ")")
    @staticmethod
    def parse(env, data):
        """Parse 'data' (either raw binary data or a BGPMessage) into
        a subclass of BGPMessage, and return the result."""

        if type(data) is not BGPMessage:
            # parse it to get type & payload first
            data = BGPMessage(env, data)

        if data.type == msg_type.OPEN:
            return(BGPOpen(env, data))
        elif data.type == msg_type.UPDATE:
            return(BGPUpdate(env, data))
        elif data.type == msg_type.NOTIFICATION:
            return(BGPNotification(env, data))
        elif data.type == msg_type.KEEPALIVE:
            return(BGPKeepalive(env, data))
        elif data.type == msg_type.ROUTE_REFRESH:
            return(BGPRouteRefreshMsg(env, data))
        else:
            # unfamiliar type, this is the best we can do
            return(data)

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
            BGPThing.__init__(self, env, msg.raw)
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
                parm = BGPParameter(env, pt, pc.get_bytes(pl))
                parm = BGPParameter.parse(env, parm)
                self.parms.append(parm)
        elif len(args) == 5:
            # By fields (version, my_as, hold_time, peer_id, parms).
            # Given that, format the raw stuff.
            (self.version, self.my_as, self.hold_time, self.peer_id,
             self.parms) = args
            ba = bytearray()
            ba.append(self.version)
            if self.my_as < 65536:
                bmisc.ba_put_be2(ba, self.my_as)
            else:
                bmisc.ba_put_be2(ba, AS_TRANS)
            bmisc.ba_put_be2(ba, self.hold_time)
            ba.append(self.peer_id[0])
            ba.append(self.peer_id[1])
            ba.append(self.peer_id[2])
            ba.append(self.peer_id[3])
            pl = 0
            for parm in self.parms: pl += len(parm.raw)
            if pl > 255:
                raise Error("Optional parameters too long")
            ba.append(pl)
            for parm in self.parms: ba += bytes(parm.raw)
            BGPMessage.__init__(self, env, msg_type.OPEN, ba)
        else:
            raise Exception("BGPOpen() bad parameters")
    def __str__(self):
        return("msg(type=" + msg_type.value2name(self.type) +
               ", version=" + str(self.version) +
               ", my_as=" + str(self.my_as) +
               ", hold_time=" + str(self.hold_time) +
               ", peer_id=" + (".".join(map(str, self.peer_id))) +
               ", parms=[" +
               (", ".join(map(str, self.parms))) + "])")

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
            BGPThing.__init__(self, env, msg.raw)
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
            if len(baa) > 65535:
                raise Exception("BGPUpdate too many attributes to fit")
            bmisc.ba_put_be2(ba, len(baa))
            ba += baa
            BGPUpdate.format_routes(env, ba, self.nlri)
            BGPMessage.__init__(self, env, msg_type.UPDATE, ba)
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
            nbytes = (nbits + 7) >> 3
            if len(pc) < nbytes:
                raise Exception("Truncated address in " + inwhat +
                                " in BGPUpdate")
            bs = list(pc.get_bytes(nbytes))
            # mask out padding bits in the last byte, if any
            if nbits & 7:
                bs[-1] &= 254 << (7 - (nbits & 7))
            # and record that in 'res'
            res.append(IPv4Prefix(env, bytes(bs), nbits))
        return(res)
    @staticmethod
    def format_routes(env, ba, rtes):
        """Format a collection of routes rtes into a bytearray ba."""
        for rte in rtes:
            ba += rte.raw
    @staticmethod
    def parse_attrs(env, pc):
        """Parse a collection of attributes into a list, from the
        "Path Attributes" field of the Update message."""
        res = []
        while len(pc):
            if len(pc) < 2:
                raise Exception("Truncated attribute in BGPUpdate")
            aflags = pc.get_byte()
            atype = pc.get_byte()
            if aflags & attr_flag.Extended_Length:
                if len(pc) < 2:
                    raise Exception("Truncated attribute length in BGPUpdate")
                alen = pc.get_be2()
            else:
                if len(pc) < 1:
                    raise Exception("Truncated attribute length in BGPUpdate")
                alen = pc.get_byte()
            if len(pc) < alen:
                raise Exception("Truncated attribute value in BGPUpdate")
            aval = pc.get_bytes(alen)
            res.append(BGPAttribute(env, aflags, atype, aval))
        return(res)
    @staticmethod
    def format_attrs(env, ba, attrs):
        """Format a collection of attributes attrs into a bytearray ba."""
        for attr in attrs:
            ba += attr.raw

class BGPKeepalive(BGPMessage):
    """A BGP keepalive message -- see RFC 4271 4.4."""
    __slots__ = []
    def __init__(self, env, msg = None):
        if msg is not None:
            # A BGPMessage; further parse its payload field.
            # Which should just be empty in a keepalive.
            if len(msg.payload) > 0:
                raise Exception("BGPKeepalive has non empty payload")
            BGPThing.__init__(self, env, msg.raw)
            self.type = msg.type
            self.payload = msg.payload
        else:
            # By fields, of which a keepalive has none.
            BGPMessage.__init__(self, env, msg_type.KEEPALIVE, bytes())
    def __str__(self):
        return("msg(type=" + msg_type.value2name(self.type) + ")")

class BGPNotification(BGPMessage):
    """A BGP notification message -- see RFC 4271 4.5."""
    __slots__ = ["error_code", "error_subcode", "data"]
    def __init__(self, env, *args):
        if len(args) == 1:
            # A BGPMessage; further parse its payload field.
            msg = args[0]
            BGPThing.__init__(self, env, msg.raw)
            self.type = msg.type
            self.payload = msg.payload
            pc = ParseCtx(self.payload)
            if len(pc) < 2:
                raise Exception("BGPNotification truncated payload")
            self.error_code = pc.get_byte()
            self.error_subcode = pc.get_byte()
            self.data = bytes(pc)
        elif len(args) == 2 or len(args) == 3:
            # By fields: error code, error subcode, and maybe data.  Given
            # that, format the raw stuff.
            (self.error_code, self.error_subcode, self.data) = args
            self.error_code &= 255
            self.error_subcode &= 255
            self.data = bytes(self.data)
            ba = bytearray()
            ba.append(self.error_code)
            ba.append(self.error_subcode)
            ba += self.data
            BGPMessage.__init__(self, env, msg_type.NOTIFICATION, ba)
        else:
            raise Exception("BGPNotification() bad parameters")
    def __str__(self):
        # Print out details of the notification.
        # describe the subcode -- how, depends on the error code
        if self.error_code == err_code.msghdr:
            sub = ", sub="+err_sub_msghdr.value2name(self.error_subcode)
        elif self.error_code == err_code.opnmsg:
            sub = ", sub="+err_sub_opnmsg.value2name(self.error_subcode)
        elif self.error_code == err_code.updmsg:
            sub = ", sub="+err_sub_updmsg.value2name(self.error_subcode)
        elif self.error_code == err_code.fsm:
            sub = ", sub="+err_sub_fsm.value2name(self.error_subcode)
        elif self.error_code == err_code.cease:
            sub = ", sub="+err_sub_cease.value2name(self.error_subcode)
        elif self.error_code == err_code.rfrmsg:
            sub = ", sub="+err_sub_rfrmsg.value2name(self.error_subcode)
        else:
            # hold timer expired (which has no subcodes); or, unknown
            # error code: represent nonzero subcodes numerically, and
            # just show nothing for zero
            if self.error_subcode != 0:
                sub = ", sub="+str(self.error_subcode)
            else:
                sub = ""

        # describe "data" -- in hex for now, if nonempty
        if len(self.data):
            data = ", data=" + ".".join(map("{:02x}".format, self.data))
        else:
            data = ""

        # describe the rest & put it all together
        return("msg(type=" + msg_type.value2name(self.type) +
               ", err=" + err_code.value2name(self.error_code) +
               sub + data + ")")

class BGPRouteRefreshMsg(BGPMessage):
    """A BGP route refresh message -- see RFC 2918 3."""
    __slots__ = ["afi", "safi"]
    def __init__(self, env, *args):
        if len(args) == 1:
            # A BGPMessage; further parse its payload field
            msg = args[0]
            BGPThing.__init__(self, env, msg.raw)
            self.type = msg.type
            self.payload = msg.payload
            pc = ParseCtx(self.payload)
            if len(pc) != 4:
                raise Exception("BGPRouteRefresh off length")
            self.afi = pc.get_be2()
            pc.get_byte() # ignore reserved byte
            self.safi = pc.get_byte()
        elif len(args) == 2:
            # By fields: afi & safi.  Given them, format the raw stuff.
            (self.afi, self.safi) = args
            self.afi &= 65535
            self.safi &= 255
            ba = bytearray()
            bmisc.ba_put_be2(ba, self.afi)
            ba.append(0)
            ba.append(self.safi)
            BGPMessage.__init__(self, env, msg_type.ROUTE_REFRESH, ba)
        else:
            raise Exception("BGPRouteRefresh() bad parameters")
    def __str__(self):
        return("msg(type=" + msg_type.value2name(self.type) +
               ", afi=" + afis.value2name(self.afi) +
               ", safi=" + safis.value2name(self.safi) + ")")
        return(BGPMessage.__str__(self))

## ## ## BGP Parameters (e.g., capabilities)

class BGPParameter(BGPThing):
    """A BGP optional parameter as found in the open message --
    see RFC 4271 4.2."""
    __slots__ = ["type", "value"]
    def __init__(self, env, *args):
        if len(args) == 1:
            # From raw binary data
            raise Exception("not yet implemented - parameter from raw")
        elif len(args) == 2:
            # from type & value
            # YYY rebuilding the raw part after parsing is a waste
            self.type, self.value = args
            self.value = bytes(self.value)
            self.type &= 255;
            if len(self.value) > 255:
                raise Exception("parameter value too long")
            ba = bytearray()
            ba.append(self.type)
            ba.append(len(self.value))
            ba += self.value
            BGPThing.__init__(self, env, ba)
        else:
            raise Exception("BGPParameter() bad parameters")
    def bgp_thing_type(self): return(BGPParameter)
    def bgp_thing_type_str(self): return("parm")
    def __str__(self):
        vhx = ".".join(map("{:02x}".format, self.value))
        return("parm(type=" + bgp_parms.value2name(self.type) +
               ", value=" + vhx + ")")
    @staticmethod
    def parse(env, data):
        """Parse 'data' (a BGPParameter) into a subclass of BGPParameter,
        and return the result."""
       
        if data.type == bgp_parms.Capabilities:
            return(BGPCapabilities(env, data))
        else:
            # unfamiliar type (or uncommon type "Authentication"), this is
            # the best we can do
            return(data)

class BGPCapabilities(BGPParameter):
    """A BGP capability advertisement parameter -- see RFC 5492."""
    __slots__ = ["caps"]
    def __init__(self, env, *args):
        """Initialize a BGP capabilities parameter."""
        if len(args) == 1 and type(args[0]) is BGPParameter:
            # A BGPParameter; further parse its 'value' field.
            # Intentionally doesn't check its type.
            parm = args[0]

            # fields in BGPThing and BGPParameter
            BGPThing.__init__(self, env, parm.raw)
            self.type = parm.type
            self.value = parm.value

            # capabilities encoded in 'parm.value'
            self.caps = []
            pc = ParseCtx(parm.value)
            while len(pc):
                if len(pc) < 2:
                    raise Exception("Truncated capability in BGPCapabilities")
                capcode = pc.get_byte()
                caplen = pc.get_byte()
                if len(pc) != caplen:
                    raise Exception("Truncated capability in BGPCapabilities")
                capval = pc.get_bytes(caplen)
                self.caps.append(BGPCapability(env, capcode, capval))
        elif len(args) == 1:
            # An iterable of BGPCapability objects: build the parameter
            # out of them.
            self.caps = args[0]
            parmval = bytearray()
            for cap in self.caps:
                parmval.append(cap.code)
                capval = bytes(cap.val)
                if len(capval) > 255:
                    raise Exception("Overlong capability in BGPCapabilities")
                parmval.append(len(capval))
                parmval += capval
            BGPParameter.__init__(self, env, bgp_parms.Capabilities, parmval)
        else:
            raise Exception("BGPCapabilities() bad parameters")
    def __str__(self):
        return("caps(" + (", ".join(map(str, self.caps))) + ")")

class BGPCapability(BGPThing):
    """A single BGP capability found in a Capabilities parameter -- see
    RFC 5492 and others."""
    __slots__ = ["code", "val"]
    def __init__(self, env, *args):
        if len(args) == 1:
            # from raw binary data
            raise Exception("BGPCapability() from raw not implemented")
        elif len(args) == 2:
            # from capability code & value
            # YYY rebuilding the raw part after parsing is a waste
            self.code = int(args[0])
            if args[1] is None:
                self.val = b""
            else:
                self.val = bytes(args[1])

            ba = bytearray()
            ba.append(self.code)
            ba += self.val
            BGPThing.__init__(self, env, ba)
        else:
            raise Exception("BGPCapability() bad parameters")
    def bgp_thing_type(self): return(BGPCapability)
    def bgp_thing_type_str(self): return("capability")
    def __str__(self):
        vhx = ".".join(map("{:02x}".format, self.val))
        return("cap(type=" + capabilities.value2name(self.code) +
               ", val=" + vhx + ")")

## ## ## BGP Attributes (as found in UPDATE)

class BGPAttribute(BGPThing):
    """A BGP attribute as found in the update message -- see
    RFC 4271 4.3 and 5."""
    __slots__ = ["flags", "type", "val"]
    def __init__(self, env, *data):
        if len(data) == 1:
            # from raw binary data
            raise Exception("not yet implemented - attribute from raw")
        elif len(data) == 3:
            # from flags, type, value
            # YYY rebuilding the raw part after parsing is a waste
            self.flags, self.type, self.val = data
            self.flags &= 255
            self.val = bytes(self.val)
            if len(self.val) > 65535:
                raise Exception("BGPAttribute -- value too long")
            elif len(self.val) > 255:
                self.flags |= attr_flag.Extended_Length
            ba = bytearray()
            ba.append(self.flags)
            ba.append(self.type)
            if self.flags & attr_flag.Extended_Length:
                bmisc.ba_put_be2(ba, len(self.val))
            else:
                ba.append(len(self.val))
            ba += self.val
            BGPThing.__init__(self, env, ba)
        else:
            raise Exception("BGPAttribute() bad parameters")
    def bgp_thing_type(self): return(BGPAttribute)
    def bgp_thing_type_str(self): return("attribute")
    def __str__(self):
        vhx = ".".join(map("{:02x}".format, self.val))
        return("attr(type=" + attr_code.value2name(self.type) +
               ", val=" + vhx + ")")
    # XXX it'd be (rather) nice to decode common attributes like AS_PATH, AS4_PATH, NEXT_HOP

## ## ## AS Path representation

class ASPath(BGPThing):
    """An AS path as found in the AS_PATH and AS4_PATH attributes in BGP.
    See RFC4271 5.1.2 and RFC6793 3.  The notation this software uses
    in string representations, however, is nonstandard and primitive,
    as follows:
                A sequence of numbers separated by commas makes up an
                AS_SEQUENCE segment.
                Precede with "set," to make it an AS_SET segment instead.
                Use "/" to separate multiple segments.
                Likewise "cseq," and "cset," prefixes make
                it AS_CONFED_SEQUENCE & AS_CONFED_SET (see RFC 5065).
    """

    # Internal representation of the AS path:
    # 'segs' - list of segments; each is a tuple containing segment type
    # and a list of AS numbers
    # 'two' - whether all its AS numbers fit in 2-byte format

    __slots__ = ["segs", "two"]

    def __init__(self, env, *args):
        """Initialize either from raw byte data, or a string, or
        a list of segments, each a tuple containing segment type and
        a list of AS numbers."""

        if len(args) > 1:
            # multiple arguments, each a segment; handle as a list of segments
            arg = args
        else:
            # one argument
            arg = args[0]

        # if the argument is a string, parse it as user input
        if args[0] is "":
            # Special case: empty AS path
            self.segs = []
            self.two = True

            BGPThing.__init__(self, env, self.make_binary_rep(env))
            return
        elif type(args[0]) is str:
            self.segs = []
            self.two = True

            for segstr in arg.split("/"):
                ases = segstr.split(",")
                as_nums = []
                # handle segment type if any
                if ases[0] == "set":
                    seg_type = path_seg_type.AS_SET
                    ases[:1] = []
                elif ases[0] == "cseq":
                    seg_type = path_seg_type.AS_CONFED_SEQUENCE
                    ases[:1] = []
                elif ases[0] == "cset":
                    seg_type = path_seg_type.AS_CONFED_SET
                    ases[:1] = []
                else:
                    seg_type = path_seg_type.AS_SEQUENCE

                # handle AS numbers
                for as_str in ases:
                    as_num = bmisc.parse_as(as_str)
                    if as_num > 65535: self.two = False
                    as_nums.append(as_num)

                self.segs.append((seg_type, as_nums))

            BGPThing.__init__(self, env, self.make_binary_rep(env))
            return

        # if the argument can be treated as a bunch of bytes, parse it
        # as protocol data
        is_bytes = False
        try:
            arg = bytes(arg)
            is_bytes = True
        except: pass

        if is_bytes:
            BGPThing.__init__(self, env, arg)
            pc = ParseCtx(self.raw)
            self.segs = []
            self.two = True
            while len(pc) > 0:
                if len(pc) < 2:
                    raise Exception("ASPath: missing or extra bytes")
                seg_type = pc.get_byte()
                seg_len = pc.get_byte() # number of AS numbers
                as_nums = []
                for i in seg_len:
                    if env.as4:
                        # 4-byte AS number
                        if len(pc) < 4:
                            raise Exception("ASPath: missing or extra bytes")
                        as_num = pc.get_be4()
                    else:
                        # 2-byte AS number
                        if len(pc) < 2:
                            raise Exception("ASPath: missing or extra bytes")
                        as_num = pc.get_be2()
                    as_nums.append(as_num)
                    if as_num > 65535: self.two = False
                self.segs.append((seg_type, as_nums))
            return

        # if the argument can be treated as an iterable, build an AS path
        is_iterable = False
        try:
            arg = iter(arg)
            is_iterable = True
        except: pass

        if is_iterable:
            self.segs = list(arg)
            self.two = True
            for seg_type, as_nums in self.segs:
                for as_num in as_nums:
                    if as_num > 65535: self.two = False
            BGPThing.__init__(self, env, self.make_binary_rep(env))
            return

        # what is it then? nothing we know how to handle
        raise Exception("ASPath bad constructor parameters")

    def make_binary_rep(self, env):
        "Generate binary representation of self, using settings in env."

        ba = bytearray()
        for seg_type, as_nums in self.segs:
            ba.append(seg_type)
            ba.append(len(as_nums))
            for as_num in as_nums:
                if env.as4:
                    # 4-byte AS format
                    bmisc.ba_put_be4(ba, as_num)
                elif as_num < 65536:
                    # 2-byte AS format
                    bmisc.ba_put_be2(ba, as_num)
                else:
                    # 2-byte AS format, doesn't fit
                    bmisc.ba_put_be2(ba, AS_TRANS)

        return(ba)

    def bgp_thing_type(self): return(ASPath)
    def bgp_thing_type_str(self): return("as_path")
    def __str__(self):
        "convert to string representation"
        seg_strs = []
        for seg_type, as_nums in self.segs:
            sub_strs = []
            if seg_type == path_seg_type.AS_SET:
                sub_strs.append("set")
            elif seg_type == path_seg_type.AS_CONFED_SEQUENCE:
                sub_strs.append("cseq")
            elif seg_type == path_seg_type.AS_CONFED_SET:
                sub_strs.append("cset")
            elif seg_type == path_seg_type.AS_SEQUENCE:
                pass
            else:
                sub_strs.append("???seg_type_"+str(int(seg_type))+"???")
            for as_num in as_nums:
                sub_strs.append(str(int(as_num)))
            seg_strs.append(",".join(sub_strs))
        return("/".join(seg_strs))

    def fourify(self, env, drop):
        """Return another ASPath, based on this one but modified for
        suitability for the AS4_PATH attribute.  Any AS_CONFED_* segments
        get removed; and, if 'drop' is True, the first AS is removed if it's
        in an AS_SEQUENCE segment and is less than 65536; to simulate the
        case where we pretend not to support 4-octet AS numbers."""

        segs2 = []
        for seg_type, as_nums in self.segs:
            if seg_type == path_seg_type.AS_CONFED_SEQUENCE:
                continue
            if seg_type == path_seg_type.AS_CONFED_SET:
                continue
            as_nums2 = as_nums
            if drop:
                if seg_type == path_seg_type.AS_SEQUENCE:
                    if as_nums[0] < 65536:
                        as_nums2 = as_nums[1:]
                        drop = False
            segs2.append((seg_type, as_nums2))

        return(ASPath(env, segs2))

