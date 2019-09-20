19 Sep 2019

"bgpy" is an implementation of parts of the BGP protocol in Python.
It's not a real router but it can send and receive BGP messages and
may sometimes be usable for test purposes.

bgpy is redistributable under a BSD license.

Usage examples:
python3 bgpy_clnt.py tcp-hex=1 dbg=estk dbg=sokw "@run notifier 6 0 text:foo" 10.1.1.2
python3 bgpy_clnt.py "@run idler" 10.1.1.2
python3 bgpy_clnt.py "@run idler" "@run basic_orig dest=1.(100-199).(100-199).0/24 nh=10.1.1.(80-99) slots=100 iupd=1 bupd=1 bint=0.5 aspath=(1000-1999),(2000-2999)" 10.1.1.2

