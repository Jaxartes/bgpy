19 Sep 2019

"bgpy" is an implementation of parts of the BGP protocol in Python.
It's not a real router but it can send and receive BGP messages and
may sometimes be usable for test purposes.

bgpy is redistributable under a BSD license.

Usage examples:
python3 bgpy_clnt.py local-as=1 router-id=10.1.1.1 "@run idler" 10.1.1.2
python3 bgpy_clnt.py "@run idler" "@run basic_orig dest=1.(100-199).(100-199).0/24 nh=10.1.1.(80-99) slots=100 iupd=1 bupd=1 bint=0.5 aspath=(1000-1999),(2000-2999)" 10.1.1.2
python3 bgpy_clnt.py tcp-hex=1 dbg=estk dbg=sokw "@run idler" "@after 5 run notifier 6 0 text:foo" 10.1.1.2

Limitations:
Are almost infinite in number; some of the most notable:
    + bgpy only makes one connection, to one peer, one time
        - no reconnecting
        - no multiple peers
    + bgpy doesn't implement the BGP state machine or any actual manipulation
    of routes
        - it makes the connection, reports what it receives, and sends
        what you tell it to
    + bgpy is always the one to make the connection
        - it doesn't accept the connection
        - so the peer might as well be in "passive" mode

Portability:
bgpy needs Python version 3.  I've tested using python 3.4.10.  I've tested
mainly on macOS, some on Linux.  I have reason to suspect there may be
problems on Windows, especially with the command interface on stdin.

Brief usage guide:
    Commands can be entered on stdin:
        "help" will list the commands you can issue there.
        Most notable is "run" to run one of the canned "programmes"
        that are implemented in bgpy_prog.py.
    Command line options:
        Should end with the IP address of the BGP peer.
        Other arguments:
            dbg= -- set one of the named debug flags to enable additional output
                dbg=estk -- include stack trace with error messages
                dbg=sokw -- include messages about select() and socket ops
            local-as= -- set local Autonomous System number; default: 1
            quiet=1 -- reduce output
            router-id= -- set own router id
            tcp-hex=1 -- display the bytes exchanged with peer over TCP
            @command... -- run "command..." as if it was issued on stdin
    Programmes
        These are the things that actually do something.
        See bgpy_prog.py.
