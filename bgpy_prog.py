# Jeremy Dilatush - All rights reserved.
# bgpy_prog.py - begun 5 July 2019
"""These are canned "programmes" for the BGP implementation in Python.
They're registered with the code in bgpy_clnt.py, invoked by it
through "register_programmes".  You can control them on the command
line and make various things happen."""

## ## ## Top matter

import sys, time, random

from bgpy_misc import dbg
import bgpy_misc as bmisc
import bgpy_repr as brepr
import bgpy_oper as boper

_programmes = dict()

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
        XXX add BGP "capabilities"
    """

    if client.open_sent is not None:
        pass # XXX log a message about having already sent an Open

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

    # Build a BGP Open message & queue it for sending
    msg = brepr.BGPOpen(client.env,
                        brepr.bgp_ver.FOUR, client.local_as, hold_time,
                        client.router_id, [])
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

def basic_orig_parse_as_path(env, s):
    """Parse an AS path for the "basic_orig" canned programme, in the
    notation described there."""

    ba = bytearray()
    if len(s) == 0:
        segs = [] # special case: empty
    else:
        segs = s.split("/")

    for seg in segs:
        ases = seg.split(",")
        if ases[0] == "set":
            seg_type = brepr.path_seg_type.AS_SET
            ases[:1] = []
        elif ases[0] == "cseq":
            seg_type = brepr.path_seg_type.AS_CONFED_SEQUENCE
            ases[:1] = []
        elif ases[0] == "cset":
            seg_type = brepr.path_seg_type.AS_CONFED_SET
            ases[:1] = []
        else:
            seg_type = brepr.path_seg_type.AS_SEQUENCE

        if len(ases) > 255:
            raise Exception("Too many AS numbers in a sequence")
        ba.append(seg_type)
        ba.append(len(ases))
        for as_str in ases:
            as_num = int(as_str)
            if as_num < 1 or as_num > 65535:
                raise Exception("AS number "+str(as_num)+
                                " out of range for 16 bits")
            bmisc.ba_put_be2(ba, as_num)

    return(ba)

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
            is chosen.  Notation:
                A sequence of numbers separated by commas makes up an
                AS_SEQUENCE segment.
                Precede with "set," to make it an AS_SET segment instead.
                Use "/" to separate multiple segments.
                Likewise "cseq," and "cset," prefixes make
                it AS_CONFED_SEQUENCE & AS_CONFED_SET (see RFC 5065).
            An empty AS path is permitted.
        origin=INCOMPLETE
            origin of path information; one of the following values defined
            by RFC 4271 4.3 & 5.1.1:
                IGP
                EGP
                INCOMPLETE
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
    cfg.add("slots", "Slots for tracking our routes",
            bmisc.EqualParms_parse_num_rng(mn = 1, mx = 1000000))
    cfg["slots"] = 100 # default value
    cfg.add("newdest", "% probability of new destination",
            bmisc.EqualParms_parse_num_rng(mn = 0.0, mx = 100.0,
                                           t = float, tn = "number"))
    cfg["newdest"] = 25
    cfg.add("aspath", "AS path specification",
            bmisc.EqualParms_parse_Choosable(do_concat = True))
    cfg["aspath"] = bmisc.ChoosableConcat()
    cfg.add("origin", "ORIGIN path attribute",
            bmisc.EqualParms_parse_enum(brepr.origin_code))
    cfg.parse("origin=INCOMPLETE")

    for arg in argv:
        cfg.parse(arg)

    if len(cfg["dest"]) < cfg["slots"]:
        raise Exception("\"basic_orig\" requires at least as many destinations"+
                        " as \"slots\"")

    if not cfg["nh"]:
        cfg["nh"].add(bmisc.ChoosableRange("10.0.0.1"))

    ## ## storage of current state

    # pseudorandom number generator
    prng = random.Random(time.time())

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
                                    ": OPEN received but not sent; waiting")
            else:
                if open_status[1]:
                    bmisc.stamprint(progname +
                                    ": OPEN sent but not received; waiting")
                else:
                    bmisc.stamprint(progname +
                                    ": OPEN neither sent not received; waiting")
        yield boper.NEXT_TIME

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
            attrs.append(brepr.BGPAttribute(client.env,
                                            brepr.attr_flag.Transitive,
                                            brepr.attr_code.ORIGIN,
                                            bytes([cfg["origin"]])))
            aspath = basic_orig_parse_as_path(client.env,
                                              prng.choice(cfg["aspath"]))
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
            nh_str = prng.choice(cfg["nh"])
            attrs.append(brepr.BGPAttribute(client.env,
                                            brepr.attr_flag.Transitive,
                                            brepr.attr_code.NEXT_HOP,
                                            bmisc.parse_ipv4(nh_str)))
            msg = brepr.BGPUpdate(client.env, [], attrs, [s_dest[s]])
            client.wrpsok.send(msg)
            s_full[s] = True

        # count down
        togo -= 1

_programmes["basic_orig"] = basic_orig

## ## ## Register all the canned programmes

def register_programmes(commanding):
    """register_programmes() registers all the canned programmes in
    bgpy_prog.py, with a Commanding object passed to it.  See
    bgpy_clnt.py for the Commanding object definition and for
    where this is called."""

    for pname in _programmes:
        commanding.register_programme(pname, _programmes[pname])
