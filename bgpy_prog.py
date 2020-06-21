# bgpy_prog.py - begun 5 July 2019
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
"""These are canned "programmes" for the BGP implementation in Python.
They're registered with the code in bgpy_clnt.py, invoked by it
through "register_programmes".  You can control them on the command
line and make various things happen."""

## ## ## Top matter

import sys

from bgpy_misc import dbg
import bgpy_misc as bmisc
import bgpy_repr as brepr
import bgpy_oper as boper

_programmes = dict()

sim_topo_data = None

## ## ## Canned programme: "idler"

def idler(commanding, client, argv):
    """ "idler" canned programme: Sends an Open followed by Keepalives.
    Arguments in argv:
        hold time -- Optional; an integer in decimal form specifying our
                    advertised hold time in seconds; 0 or 3 - 65535.
                    Default 180 seconds.
        keep alive ratio -- Optional; "k" followed by a number in decimal
                    form indicating the ratio between the negotiated hold
                    time, and the interval between keepalives that we send.
                    Range 1.0 up; default 3.0; recommended 3.0 up.  No matter
                    what the value here, the interval between keepalives will
                    be at least 1 second, as mandated by RFC 4271 4.4.
    """

    progname = "idler"

    hold_time = 180
    keepalive_ratio = 3.0

    # Process the arguments list.
    for arg in argv:
        e = "Unrecognized parameter " + arg
        try:
            hold_time = int(arg, 10)
            if hold_time == 0 or (hold_time >= 3 and hold_time <= 65535):
                continue
            else:
                e = "Hold time must be 0 or 3 - 65535"
        except Exception as e: pass # guess it's something else

        if arg[0] == "k":
            try:
                keepalive_ratio = float(arg[1:])
                if keepalive_ratio >= 1.0:
                    continue
                else:
                    e = "Keepalive ratio must be 1.0 or higher"
            except Exception as e: pass # guess it's something else

        # It's nothing good; 'e' says what's wrong.
        raise Exception("idler arguments error: " + e)

    # wait for a connection
    if client.listen_mode:
        bmisc.stamprint(progname + ": waiting for connection")
        while client.listen_mode:
            yield boper.NEXT_TIME

    if client.open_sent is not None:
        bmisc.stamprint(progname + ": running after Open already sent," +
                        " will send again, which isn't good")
        # It's not good, but I guess it's what you wanted...

    # We have a connection and are ready to send an Open.  I think some
    # implementations might, when on the "passive" side of the TCP connection,
    # wait for the other side's OPEN.  But RFC 4271 says "Once the TCP
    # connection is completed, it doesn't matter which end was active and
    # which was passive," so it seems we shouldn't have to wait like that.

    # If you want to delay the sending of "Open", run "idler" on a timer,
    # e.g. with "@after 60 run idler" on the command line.

    # Build a BGP Open message & queue it for sending
    open_parms = []
    capabilities = []
    if client.as4_us:
        # advertise the 4-octet AS capability (RFC6793)
        capba = bytearray()
        bmisc.ba_put_be4(capba, client.local_as)
        capabilities.append(brepr.BGPCapability(client.env,
                                                brepr.capabilities.as4,
                                                capba))
    if client.rr_us:
        # advertise the route refresh capability (RFC 2918)
        # (we don't actually implement it in bgpy)
        capabilities.append(brepr.BGPCapability(client.env,
                                                brepr.capabilities.refr,
                                                None))
    if len(capabilities) > 0:
        # advertise capabilities (RFC5492)
        open_parms.append(brepr.BGPCapabilities(client.env, capabilities))
    msg = brepr.BGPOpen(client.env,
                        brepr.bgp_ver.FOUR, client.local_as, hold_time,
                        client.router_id, open_parms)
    client.wrpsok.send(msg)
    client.open_sent = msg

    # Wait until we get a BGP Open message from the peer -- we'll use it
    # to calculate the actual hold time.
    while client.open_recv is None:
        yield(boper.NEXT_TIME)

    # Now figure out the actual hold time and keepalive interval, based
    # on the open we sent and the one we received.
    hold_time = min(client.open_sent.hold_time,
                    client.open_recv.hold_time)
    if hold_time <= 0:
        # no periodic keepalives
        keepalive_interval = None
    else:
        # periodic keepalives at the specified ratio but no more than
        # one per second
        keepalive_interval = max(1, hold_time / keepalive_ratio)

    # Now all that's left to do is send keepalives.  We send one right
    # away and then send them at intervals, no matter what else is going
    # on.  If we were more sophisticated we might delay keepalives when
    # we're sending other things instead, but we don't.
    while True:
        # Build a BGP Keepalive message & queue it for sending
        msg = brepr.BGPKeepalive(client.env)
        client.wrpsok.send(msg)

        # Indicate when to wait for before we do the next one
        if keepalive_interval is None:
            yield(None)
        else:
            yield(keepalive_interval + bmisc.tor.get())

    # XXX see to handling hold time timeout, but not here -- in client

_programmes["idler"] = idler

## ## ## Canned programme: "basic_orig"

def basic_orig(commanding, client, argv):
    """ "basic_orig" canned programme: Sends Updates carring IPv4 routes
    pseudorandomly generated according to some simple configuration.

    The configuration is in name=value pairs, as follows, with examples:
        nh=10.0.0.1
            IPv4 address to use as next hop for all routes; default 10.0.0.1.
            Can take range expressions, example 10.0.0.(2-5), but in many
            scenarios having a diversity of nexthops is abnormal.
        dest=10.(3-5).0.0/(16-20)
            Address/masklength specification of destinations to generate
            routes for.  Need at least one, can have more.
        iupd=20
            Number of updates (one route each) to send in the initial
            burst.  Default 20.
        bupd=1
            Number of updates (one route each) to send in subsequent
            bursts.  Default 1.
        bint=10
            Seconds between bursts of updates.  May be fractional.  Default 10.
        blim=0
            Limit number of subsequent bursts before ending.  No end if 0.
            Default 0 (no end).
        slots=100
            Number of "slots" for keeping track of advertised routes.
            The maximum number of routes that have been advertised and not
            withdrawn; the average number will be less.
            Default 100.
        newdest=25
            Percent probability of, when creating a new route, picking
            a new destination (instead of using the last one belonging
            to the chosen "slot").  Default 25.
        aspath=1,2,(3-5)
            AS path.  May use numeric ranges.  May specify more than
            one.  If you don't specify any a simple reasonable default
            is chosen.  See ASPath() in bgpy_repr.py for the syntax used.

            An empty AS path is permitted by this program, and in some
            cases by the standard.

            If the "sim_topo" programme has been run, its results will
            override the aspath= setting.
        as4path=1,2,3,(400000-500000)
            Not usually needed.  Normally the AS4_PATH attribute, if needed,
            is generated based on 'aspath'.  But if you want to override
            that for some weird test you can with 'as4path=...'.
        origin=INCOMPLETE
            origin of path information; one of the following values defined
            by RFC 4271 4.3 & 5.1.1:
                IGP
                EGP
                INCOMPLETE
        com=0x00010002,0x00030004
        xcom=0x0102030405060708,0x090a0b0c0d0e0f10
            Specify communities to put on the routes; all
            communities specified in a single string delimited by commas.
            "com" specifies RFC1997 communities; "xcom" specifies
            RFC4360 extended communities
        file=path/name
            Parse further name-value pairs from named file.  One pair on
            each line; ignores blank lines and lines beginning with "#".
        seed=1234
            Seed the pseudo random number generator with the specified
            string; this is optional, but can provide repeatability.
            Empty string uses a shared generator seeded from the clock.
    """

    ## configuration via name-value pairs
    progname = "basic_orig"
    cfg = bmisc.EqualParms()

    cfg.add("nh", "Next hop IPv4 address",
            bmisc.EqualParms_parse_Choosable(do_concat = True))
    cfg["nh"] = bmisc.ChoosableConcat()

    cfg.add("dest", "Destination IPv4 address range",
            bmisc.EqualParms_parse_Choosable(do_concat = True))
    cfg["dest"] = bmisc.ChoosableConcat()
    cfg.add("iupd", "Num updates in initial burst",
            bmisc.EqualParms_parse_num_rng(mn = 0))
    cfg["iupd"] = 20 # default value
    cfg.add("bupd", "Num updates per subsequent burst",
            bmisc.EqualParms_parse_num_rng(mn = 0))
    cfg["bupd"] = 1 # default value
    cfg.add("bint", "Seconds between bursts",
            bmisc.EqualParms_parse_num_rng(mn = 0.1, mx = 86400.0,
                                           t = float, tn = "number"))
    cfg["bint"] = 10.0 # default value
    cfg.add("blim", "Limit number of subsequence bursts",
            bmisc.EqualParms_parse_num_rng(mn = 0))
    cfg["blim"] = 0 # default value
    cfg.add("slots", "Slots for tracking our routes",
            bmisc.EqualParms_parse_num_rng(mn = 1, mx = 10000000))
    cfg["slots"] = 100 # default value
    cfg.add("newdest", "% probability of new destination",
            bmisc.EqualParms_parse_num_rng(mn = 0.0, mx = 100.0,
                                           t = float, tn = "number"))
    cfg["newdest"] = 25
    cfg.add("aspath", "AS path specification",
            bmisc.EqualParms_parse_Choosable(do_concat = True))
    cfg["aspath"] = bmisc.ChoosableConcat()
    cfg.add("as4path", "AS4_PATH override",
            bmisc.EqualParms_parse_Choosable(do_concat = True))
    cfg["as4path"] = bmisc.ChoosableConcat()
    cfg.add("origin", "ORIGIN path attribute",
            bmisc.EqualParms_parse_enum(brepr.origin_code))
    cfg.parse("origin=INCOMPLETE")
    cfg.add_parse_file("file", "read name-value pairs from file")
    cfg.add("com", "communities (RFC1997)",
            bmisc.EqualParms_parse_Choosable(do_concat = True))
    cfg["com"] = bmisc.ChoosableConcat()
    cfg.add("xcom", "extended communities (RFC4360)",
            bmisc.EqualParms_parse_Choosable(do_concat = True))
    cfg["xcom"] = bmisc.ChoosableConcat()
    cfg.add("seed", "pseudorandom number generation seed",
            bmisc.EqualParms_parse_PRNG)
    cfg.parse("seed=")

    for arg in argv:
        cfg.parse(arg)

    prng = cfg["seed"]

    if len(cfg["dest"]) < cfg["slots"]:
        raise Exception("\"basic_orig\" requires at least as many destinations"+
                        " as \"slots\"")

    if not cfg["nh"]:
        cfg["nh"].add(bmisc.ChoosableRange("10.0.0.1"))

    ## ## wait for OPEN messages to have been exchanged
    open_status = None
    while True:
        old_open_status = open_status
        open_status = (client.open_recv is not None,
                       client.open_sent is not None)
        if open_status != old_open_status:
            # something has happened, not enough to stop waiting,
            # but maybe worth logging
            if open_status[0]:
                if open_status[1]:
                    bmisc.stamprint(progname +
                                    ": OPEN exchange is completed; proceeding")
                    break # no need to wait any longer
                else:
                    bmisc.stamprint(progname +
                                    ": OPEN received but not yet sent; waiting")
            else:
                if open_status[1]:
                    bmisc.stamprint(progname +
                                    ": OPEN sent but not yet received; waiting")
                else:
                    bmisc.stamprint(progname +
                                    ": OPEN neither sent/received yet; waiting")
        yield boper.NEXT_TIME

    ## ## storage of current state

    # advertised route slots
    s_full = [] # True for each slot that's full
    s_dest = [] # destination used for this slot, or None if unassigned
    for slot in range(cfg["slots"]):
        s_full.append(False)
        s_dest.append(None)

    # destinations used - to avoid duplication
    dests_used = set()

    # updates to go in current burst
    togo = cfg["iupd"]
    bmisc.stamprint(progname + ": sending " + str(togo) + " initial updates")

    # burst limit
    blim = cfg["blim"]
    if blim <= 0: blim = None # no limit

    ## ## main loop sending updates & waiting
    if len(cfg["aspath"]) < 1:
        if client.local_as == client.open_recv.my_as:
            # IBGP: default as path is empty
            cfg["aspath"].add(bmisc.ChoosableRange(""))
        else:
            # EBGP: default as path has just our own AS number
            cfg["aspath"].add(bmisc.ChoosableRange(str(client.local_as)))

    while True:
        # wait at least until the outbound buffer is clear; sometimes longer
        if togo > 0:
            yield boper.WHILE_TX_PENDING
        else:
            bmisc.stamprint(progname +
                            ": waiting for "+repr(cfg["bint"])+" seconds")
            yield(cfg["bint"] + bmisc.tor.get())
            togo = cfg["bupd"]
            bmisc.stamprint(progname + ": sending " + str(togo) +
                            " periodic updates")
            if blim is not None:
                # count bursts
                blim -= 1
                if blim < 0:
                    bmisc.stamprint(progname +
                                    ": ending after " +
                                    str(cfg["blim"]) + " non-initial bursts.")
                    break
            continue

        # pick a "slot" to update; *what* we do depends on what's in the slot
        s = prng.randint(0, cfg["slots"] - 1)
        if s_full[s]:
            # Slot is full: make it empty by withdrawing the route.
            msg = brepr.BGPUpdate(client.env, [s_dest[s]], [], [])
            client.wrpsok.send(msg)
            s_full[s] = False
        else:
            # Slot is empty: make it full by advertising a route.
            if s_dest[s] is None or (prng.random() * 100.0) < cfg["newdest"]:
                # pick a new destination
                if s_dest[s] is not None:
                    dests_used.remove(s_dest[s])
                    s_dest[s] = None
                while s_dest[s] is None or s_dest[s] in dests_used:
                    # pick & parse one of the values in cfg["dest"]
                    # then we'll see if it's one we're using already
                    deststr = prng.choice(cfg["dest"])
                    s_dest[s] = brepr.IPv4Prefix(client.env, deststr)
                dests_used.add(s_dest[s])
            attrs = []

            # attribute ORIGIN
            attrs.append(brepr.BGPAttribute(client.env,
                                            brepr.attr_flag.Transitive,
                                            brepr.attr_code.ORIGIN,
                                            bytes([cfg["origin"]])))

            # attribute AS_PATH: 2 or 4 bytes per AS
            # And prepare AS4_PATH
            if sim_topo_data is not None and len(sim_topo_data) > 0:
                aspath = prng.choice(sim_topo_data)
            else:
                aspath = brepr.ASPath(client.env, prng.choice(cfg["aspath"]))
            as4path = None
            as4path_flags = (brepr.attr_flag.Transitive |
                             brepr.attr_flag.Optional)
            if (((not aspath.two) and (not client.env.as4)) or
                len(cfg['as4path'])):
                # This AS_PATH doesn't fully fit in 2-bytes-per-AS format,
                # and we're not speaking 4-bytes-per-AS.  Thus, the AS4_PATH
                # attribute is appropriate
                env4 = client.env.with_as4(True)
                if len(cfg["as4path"]) > 0:
                    as4path = brepr.ASPath(env4, prng.choice(cfg["as4path"]))
                elif client.as4_us:
                    # We admit to understanding as4, so give them everything.
                    as4path = aspath.fourify(env4, True)
                else:
                    # We're pretending not to understand 4-byte-AS; so,
                    # pretend we received this from upstream
                    as4path = aspath.fourify(env4, True)
                    as4path_flags |= brepr.attr_flag.Partial
            aspath = aspath.make_binary_rep(client.env)
            if as4path is not None and len(as4path.segs) == 0:
                # special case: "as4path=" suppresses the AS4_PATH attribute
                as4path = None
            if as4path is not None:
                as4path = as4path.make_binary_rep(env4)

            attrs.append(brepr.BGPAttribute(client.env,
                                            brepr.attr_flag.Transitive,
                                            brepr.attr_code.AS_PATH,
                                            aspath))

            if client.local_as == client.open_recv.my_as:
                # for IBGP there's the "LOCAL_PREF" attribute;
                # just use a default value of 100.
                lp = bytearray()
                bmisc.ba_put_be4(lp, 100)
                attrs.append(brepr.BGPAttribute(client.env,
                                                brepr.attr_flag.Transitive,
                                                brepr.attr_code.LOCAL_PREF,
                                                lp))

            # attribute: NEXT_HOP
            nh_str = prng.choice(cfg["nh"])
            attrs.append(brepr.BGPAttribute(client.env,
                                            brepr.attr_flag.Transitive,
                                            brepr.attr_code.NEXT_HOP,
                                            bmisc.parse_ipv4(nh_str)))

            # attribute: COMMUNITY (RFC1997)
            if len(cfg["com"]):
                communities_str = prng.choice(cfg["com"])
            else:
                communities_str = ""
            if communities_str is not "":
                communities = bmisc.parse_communities(communities_str)
                attrs.append(brepr.BGPAttribute(client.env,
                                                brepr.attr_flag.Optional|
                                                brepr.attr_flag.Transitive,
                                                brepr.attr_code.COMMUNITY,
                                                communities))

            # attribute: EXTENDED_COMMUNITIES (RFC4360)
            if len(cfg["xcom"]):
                xcommunities_str = prng.choice(cfg["xcom"])
            else:
                xcommunities_str = ""
            if xcommunities_str is not "":
                xcommunities = bmisc.parse_xcommunities(xcommunities_str)
                attrs.append(brepr.BGPAttribute(client.env,
                                                brepr.attr_flag.Optional|
                                                brepr.attr_flag.Transitive,
                                                brepr.attr_code.EXTENDED_COMMUNITIES,
                                                xcommunities))

            # attribute: AS4_PATH, only under limited circumstances
            if as4path is not None:
                attrs.append(brepr.BGPAttribute(client.env,
                                                as4path_flags,
                                                brepr.attr_code.AS4_PATH,
                                                as4path))

            msg = brepr.BGPUpdate(client.env, [], attrs, [s_dest[s]])
            client.wrpsok.send(msg)
            s_full[s] = True

        # count down
        togo -= 1

_programmes["basic_orig"] = basic_orig

## ## ## Canned programme: "notifier"

def notifier(commanding, client, argv):
    """ "notifier" canned program: sends a Notification.
    Arguments in argv:
        notification code (numeric; example: 6 for "Cease")
        notification subcode (numeric; depends on main code)
        (optional) data (hexadecimal, or "text:" followed by text)
    """

    progname = "notifier"

    if client.listen_mode:
        bmisc.stamprint(progname + ": waiting for connection")
        while client.listen_mode:
            yield boper.NEXT_TIME

    if client.open_sent is None:
        # We haven't sent an OPEN, and RFC 4271 says the first message each
        # side sends is an OPEN.  So, put one together.
        bmisc.stamprint(progname +
                        ": sending Open since it hasn't been done yet")
        msg = brepr.BGPOpen(client.env, brepr.bgp_ver.FOUR,
                            client.local_as, 180, client.router_id, [])
        client.wrpsok.send(msg)
        client.open_sent = msg

    # Parse and check argv[]
    if len(argv) < 2:
        raise Exception("notifier arguments error: too few")
    elif len(argv) > 3:
        raise Exception("notifier arguments error: too many")
    code = subcode = termsec = None
    try:
        code = int(argv[0])
    except: pass
    if code is None or code < 0 or code > 255:
        raise Exception("notifier arguments error:"+
                        " code must be integer 0-255")
    try:
        subcode = int(argv[1])
    except: pass
    if subcode is None or subcode < 0 or subcode > 255:
        raise Exception("notifier arguments error:"+
                        " subcode must be integer 0-255")
    if len(argv) < 3:
        # missing data: treat as empty
        data = bytes()
    elif argv[2][:5] == "text:":
        # literal text
        data = bytes(argv[2][5:], "utf-8")
    else:
        # hexadecimal
        if len(argv[2]) & 1:
            raise Exception("notifier arguments error:"+
                            " odd length hex data")
        ba = bytearray()
        for i in range(0, len(argv[2]), 2):
            b = None
            try:
                b = int(argv[2][i:(i+2)], base=16)
            except: pass
            if b is None:
                raise Exception("notifier arguments error:"+
                                " bad hex data")
            ba.append(b)
        data = bytes(ba)

    # build & send the notification message
    msg = brepr.BGPNotification(client.env, code, subcode, data)
    client.wrpsok.send(msg)

_programmes["notifier"] = notifier

## ## ## Canned programme: "sim_topo"

def sim_topo(commanding, client, argv):
    """ "sim_topo" canned programme: Generates AS paths which another
    programme like "basic_orig" can use for the routes it
    generates and sends out.  The intention is a little more verisimilitude
    than you can get into such a program through its own configuration
    options.

    The result, once available, is then made available to other programmes
    that want it, in 'sim_topo_data', a sequence of bmisc.ASPath() objects
    for use.

    Name=value parameters taken by sim_topo:
        nodes=10
            number of virtual routers to create including us
        as=(1000-3000)
            AS numbers to use, other than our own
        linking=2.5
            typical number of neighbors each node is linked to
        dump=1
            dump the table we generated to the log as soon as we've got it
        seed=1234
            Seed the pseudo random number generator with the specified
            string; this is optional, but can provide repeatability.
            Empty string uses a shared generator seeded from the clock.
    """

    global sim_topo_data

    ## configuration via name-value pairs
    progname = "sim_topo"
    cfg = bmisc.EqualParms()
    cfg.add("nodes", "Number of virtual routers",
            bmisc.EqualParms_parse_num_rng(mn=3, mx=1000000))
    cfg["nodes"] = 25
    cfg.add("as", "AS numbers other than our own",
            bmisc.EqualParms_parse_Choosable(do_concat = True))
    cfg["as"] = bmisc.ChoosableConcat()
    cfg.add("linking", "Typical number of neighbors per node",
            bmisc.EqualParms_parse_num_rng(t = float, mn = 2, mx = 100))
    cfg["linking"] = 2.5
    cfg.add("dump", "Dump result to log",
            bmisc.EqualParms_parse_num_rng(mn = 0, mx = 1))
    cfg["dump"] = 0
    cfg.add("seed", "pseudorandom number generation seed",
            bmisc.EqualParms_parse_PRNG)
    cfg.parse("seed=")

    for arg in argv:
        cfg.parse(arg)

    prng = cfg["seed"]

    if len(cfg["as"]) == 0:
        cfg.parse("as=(1000-1999)")

    if len(cfg["as"]) < cfg["nodes"] * 1.1 + 10:
        raise Exception("'as' setting needs a bigger range"+
                        " to handle this many 'nodes'")

    ## wait for connection to be established before doing anything
    while ((client.open_recv is None) or (client.open_sent is None)):
        yield boper.NEXT_TIME

    ## now we know local and remote AS numbers, iBGP/eBGP etc, and can proceed
    las = client.local_as
    ras = client.open_recv.my_as
    ibgp = (las == ras)
    if ibgp:
        ibgpword = "iBGP"
    else:
        ibgpword = "EBGP"
    bmisc.stamprint(progname +
                    ": local as "+str(las)+", remote as "+str(ras)+
                    " this is "+ibgpword)

    ## link all the nodes together

    # internal data structures:
    #       result - triples of IPv4 addr, IPv6 addr, ASPath(); will
    #               be exported as sim_topo_data once it's filled in
    #       links - for each node, list of its linked neighbors
    #       partition - which nodes can reach which others
    result = set()
    links = list(map(lambda n: [], range(cfg["nodes"])))
    partition = bmisc.Partition(range(cfg["nodes"]))
    links_todo = int((cfg["nodes"] * cfg["linking"] + 1) / 2)
    initial_links_todo = cfg["nodes"] - 1

    # initial links to join everything together
    while initial_links_todo > 0:
        yield(boper.RIGHT_NOW) # let events be processed

        # pick two nodes that can't reach each other yet
        n1 = prng.randrange(0, cfg["nodes"])
        n2 = prng.randrange(0, cfg["nodes"])
        if partition.sub_same(n1, n2):
            continue

        # link these two
        links_todo -= 1
        initial_links_todo -= 1
        links[n1].append(n2)
        links[n2].append(n1)
        partition.sub_join(n1, n2)

    ## additional links as desired
    while links_todo > 0:
        yield(boper.RIGHT_NOW) # let events be processed

        n1 = prng.randrange(0, cfg["nodes"])
        n2 = prng.randrange(0, cfg["nodes"])
        if n1 != n2 and n1 not in links[n2]:
            # make a link
            links_todo -= 1
            links[n1].append(n2)
            links[n2].append(n1)
        elif prng.randrange(0, 5) < 1:
            # pretend we made a link, so we don't get stuck forever
            links_todo -= 1

    ## pick AS numbers for nodes

    #       as_nums - for each node, its AS number
    as_nums = [None] * cfg["nodes"]

    # I'm node zero.
    as_nums[0] = las

    # pick AS numbers for all the other nodes
    as_seen = {las, ras}
    for n in range(1, cfg["nodes"]):
        yield bmisc.tor.get() # let events be processed

        # pick an AS number we haven't used yet
        while True:
            a_s = int(prng.choice(cfg["as"]))
            if a_s not in as_seen:
                break

        # put it on
        as_nums[n] = a_s
        as_seen.add(a_s)

    ## build the result: an AS path to each node

    data = [None] * cfg["nodes"] # AS path data, for now as strings
    if ibgp:
        data[0] = []
    else:
        data[0] = [as_nums[0]]

    nodes_to_path = cfg["nodes"] - 1
    while nodes_to_path > 0:
        yield(boper.RIGHT_NOW) # let events be processed

        # Pick a node and one of its neighbors.  If we have a path for
        # the first and not the second, make a path for the second.
        n = prng.randrange(cfg["nodes"])
        if data[n] is None:
            continue
        nn = prng.choice(links[n])
        if data[nn] is not None:
            continue
        data[nn] = data[n] + [as_nums[nn]]
        nodes_to_path -= 1

    # now convert that data to ASPath()
    for n in range(cfg["nodes"]):
        data[n] = brepr.ASPath(client.env, ",".join(map(str, data[n])))

    # dump the result if configured to do so
    if cfg["dump"]:
        for n in range(cfg["nodes"]):
            bmisc.stamprint(progname + ": node " + str(n) +
                            " path " + str(data[n]) + " neigh " +
                            (",".join(map(str, links[n]))))

    # put the result on
    sim_topo_data = data

    # that's all
    bmisc.stamprint(progname + ": done; provided data")

    # There are some notable inefficiencies in "sim_topo", esp how when
    # it tries to pick a node for something it just picks one and sees
    # if it's suitable, and if it's not repeats until it finds one.
    # But testing shows them not to be that severe (nodes=100000 takes
    # 170 seconds in my test) and doing something about it would make
    # the code more complicated.


_programmes["sim_topo"] = sim_topo

## ## ## Register all the canned programmes

def register_programmes(commanding):
    """register_programmes() registers all the canned programmes in
    bgpy_prog.py, with a Commanding object passed to it.  See
    bgpy_clnt.py for the Commanding object definition and for
    where this is called."""

    for pname in _programmes:
        commanding.register_programme(pname, _programmes[pname])
