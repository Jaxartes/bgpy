# Jeremy Dilatush - All rights reserved.
# bgpy_prog.py - begun 5 July 2019
"""These are canned "programmes" for the BGP implementation in Python.
They're registered with the code in bgpy_clnt.py, invoked by it
through "register_programmes".  You can control them on the command
line and make various things happen."""

## ## ## Top matter

import sys
import time

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

def basic_orig(commanding, client, argv):
    """ "basic_orig" canned programme: Sends Updates carring IPv4 routes
    pseudorandomly generated according to some simple configuration.

    The configuration is in name=value pairs, as follows, with examples:
        nh=10.0.0.1
            IPv4 address to use as next hop for all routes; default 10.0.0.1.
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
        as_path=1,2,(3-5)
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
    """

    ## storage for configuration

    c_nh = "XXX 10.0.0.1"
    c_dests = ChoosableConcat()
    c_iupd = 20
    c_bupd = 1
    c_bint = 10
    c_slots = 100
    c_newdest = 25.0
    c_as_path = ChoosableConcat()

    ## parse name=value pairs in the arguments

    XXX

_programmes["basic_orig"] = basic_orig

## ## ## Register all the canned programmes

def register_programmes(commanding):
    """register_programmes() registers all the canned programmes in
    bgpy_prog.py, with a Commanding object passed to it.  See
    bgpy_clnt.py for the Commanding object definition and for
    where this is called."""

    for pname in _programmes:
        commanding.register_programme(pname, _programmes[pname])
