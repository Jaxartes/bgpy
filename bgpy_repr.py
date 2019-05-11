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
from bgpy_misc import ConstantSet

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

## ## ## BGP Configuration-like State

class BGPEnv(object):
    """A handful of settings that impact how BGP handles things:
        as4 -- whether 4 byte AS numbers are in use
    """
    def __init__(self, cpy = None):
        if cpy is None:
            self.as4 = False
        else:
            self.as4 = cpy.as4

## ## ## BGP Messages

def get_bgp_msg(sok):
    # Retrieve a BGP message from a socket, and return it.
    # XXX gets it in binary form & then calls something else to parse it
    pass

