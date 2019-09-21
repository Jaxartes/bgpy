19 Sep 2019

"bgpy" is an implementation of parts of the BGP protocol in Python.
It's not a real router but it can send and receive BGP messages and
may sometimes be usable for test purposes.

bgpy is redistributable under a BSD license.

Usage examples:
python3 bgpy_clnt.py local-as=1 router-id=10.1.1.1 "@run idler" 10.1.1.2
python3 bgpy_clnt.py "@run idler" "@run basic_orig dest=1.(100-199).(100-199).0/24 nh=10.1.1.(80-99) slots=100 iupd=1 bupd=1 bint=0.5 aspath=(1000-1999),(2000-2999)" 10.1.1.2
python3 bgpy_clnt.py tcp-hex=1 dbg=estk dbg=sokw "@run notifier 6 0 text:foo" 10.1.1.2

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
