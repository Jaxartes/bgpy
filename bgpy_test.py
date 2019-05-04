# Jeremy Dilatush - All rights reserved.
# bgpy_test.py - begun 4 May 2019
"""Tests for code in bgpy.  How much I write of this is uncertain.  I generally
prefer testing code "in use" rather than piece by piece (the proof of the
pudding is in the eating).  In the case of bgpy, operating sanely and as
intended when connected to a real BGP implementation is the goal."""

## ## ## Top matter

import sys
from sys import stderr
import time
import bgpy_misc as bmisc

class TestFailureError(Exception):
    def __init__(self, msg = "Mismatch, test failed", g = None, e = None):
        if g is not None:
            msg += ", got "+repr(g)+" exp "+repr(e)
        super().__init__(self, msg)

## ## ## Test bmisc.supersplit()

# list of inputs & expected outputs
supersplit_tv = [
    (("one two three",), ["one", "two", "three"]),
    (("one two three", "w"), ["one", "t"]),
    (("  one two  three four  ",), ["one", "two", "three", "four"]),
    (("  one two  three four  ", "f"), ["one", "two", "three"]),
    ((" one \"two three\" four",), ["one", "two three", "four"]),
    (("",), []),
    (("    \t    ",), []),
    (("    \t    ", "\t"), []),
    (("\t    ", "\t"), []),
    (("alpha\nbeta\\\\gamma\ndelta",), ["alpha", "beta\\gamma", "delta"]),
    (("alpha\nbeta\\ygammaydelta", "y"), ["alpha", "betaygamma"]),
    (("alpha\\ beta gamma\\ delta",), ["alpha beta", "gamma delta"]),
    (("this \"is \\a\" te\\163\\x74",), ["this", "is \a", "test"]),
    (("w\\u0078yz\\r\\n\\b\\t",), ["wxyz\r\n\b\t"])
]
def supersplit_test(tv = supersplit_tv):
    """Test bmisc.supersplit()"""
    for (i, x) in tv:
        print("bmisc.supersplit"+str(i)+" expecting "+str(x), file=stderr)
        g = bmisc.supersplit(*i)
        if g != x:
            print("got: "+str(g), file=stderr)
            raise TestFailureError()
    print("supersplit_test completed ok", file=stderr)

## ## ## Test bmisc.ConstantSet()

def ConstantSet_test():
    # A ConstantSet we'll use in these tests
    cs = bmisc.ConstantSet(
        ("one", "First", 1),
        ("two", "Second", 2),
        ("three", "Third", 3),
        four=4, five=5, six=6
    )
    # Values expected to match
    tests = [
        (cs.one, 1, "one", "First"),
        (cs.two, 2, "two", "Second"),
        (cs.three, 3, "three", "Third"),
        (cs.four, 4, "four", "four"),
        (cs.five, 5, "five", "five"),
        (cs.six, 6, "six", "six")
    ]
    for (v, xv, xsn, xpn) in tests:
        print("cs."+xsn+" => "+str(v)+" exp "+str(xv), file=stderr)
        if v != xv: raise TestFailureError()
        gsn = cs.value2name(xv)
        print("cs.value2name("+str(xv)+") => "+str(gsn)+ " exp "+str(xsn),
              file=stderr)
        if gsn != xsn: raise TestFailureError()
        gpn = cs.value2printable_name(xv)
        print("cs.value2printable_name("+str(xv)+") => "+str(gpn)+
              " exp "+str(xpn), file=stderr)
        if gpn != xpn: raise TestFailureError()
    print("ConstantSet_test completed ok", file=stderr)

## ## ## Test bmisc.ParseCtx()

def ParseCtx_test():
    """Test the ParseCtx class and the main stuff it has"""
    ParseCtx_test1()
    ParseCtx_test2()
    ParseCtx_test3()
    print("ParseCtx_test completed ok", file=stderr)

# test vector for ParseCtx_test1(): input to constructor; expected
# exception / buf, pos, end, as4 values
ParseCtx_tv1 = [
    ((b"one",),
     (b"one", 0, 3, False)),
    ((bmisc.ParseCtx(b"two"),),
     (b"two", 0, 3, False)),
    ((bmisc.ParseCtx(b"three", 1, 3, 1),),
     (b"three", 1, 3, True)),
    ((b"four", 2, 2, 0),
     (b"four", 2, 2, False)),
    ((None,),
     TypeError),
    ((bmisc.ParseCtx(b"five-six", 2, 4), None, 1, True),
     (b"five-six", 2, 3, True)),
    ((bmisc.ParseCtx(b"seven-eight", 3, 8, 1), 1, None, False),
     (b"seven-eight", 4, 8, False)),
    ((bmisc.ParseCtx(b"nine-ten", 2), 1.5),
     TypeError),
    ((bmisc.ParseCtx(b"nine-ten", 2), None, 1.5),
     TypeError),
    ((bmisc.ParseCtx(b"nine-ten", 2), 2, 3),
     (b"nine-ten", 4, 5, False)),
    ((bmisc.ParseCtx(b"nine-ten", 2), 2, 2),
     (b"nine-ten", 4, 4, False)),
    ((bmisc.ParseCtx(b"nine-ten", 2), 3, 2),
     IndexError),
]

def ParseCtx_test1():
    """Test the ParseCtx class constructor"""
    # test vector: input & expected exception / buf, pos, end, as4 values
    for (i, x) in ParseCtx_tv1:
        gx = g = "weird failure"
        try:
            gg = bmisc.ParseCtx(*i)
            g = (gg.buf, gg.pos, gg.end, gg.as4)
            gx = x
        except Exception as e:
            g = type(e)
            gx = e
        print("ParseCtx"+str(i), file=stderr)
        print("   => "+repr(gx), file=stderr)
        print("  exp "+str(x), file=stderr)
        if g != x: raise TestFailureError()

    print("ParseCtx_test1 completed ok", file=stderr)

# test vector for ParseCtx_test2(): ParseCtx, expected results of
# repr, bytes, dump
ParseCtx_tv2 = [
    (bmisc.ParseCtx(b""),
     "ParseCtx(b'')", b"", "ParseCtx{b''[0:0],as4=False}"),
    (bmisc.ParseCtx(b"xyz", 1, as4=1),
     "ParseCtx(b'yz')", b"yz", "ParseCtx{b'xyz'[1:3],as4=True}"),
    (bmisc.ParseCtx(b"alpha", 0, 3, as4=0),
     "ParseCtx(b'alp')", b"alp", "ParseCtx{b'alpha'[0:3],as4=False}"),
    (bmisc.ParseCtx(b"beta", 1, 1),
     "ParseCtx(b'')", b"", "ParseCtx{b'beta'[1:1],as4=False}"),
]

def ParseCtx_test2():
    """Tests the following methods of bmisc.ParseCtx:
    __repr__, __bytes__, dump, and the nonexistent __str__"""

    for (i, xr, xb, xd) in ParseCtx_tv2:
        xs = xr

        gr = repr(i)
        print("repr("+i.dump()+") => "+str(gr)+" exp "+str(xr),
              file=stderr)
        if gr != xr: raise TestFailureError()

        gb = bytes(i)
        print("bytes("+i.dump()+") => "+str(gb)+" exp "+str(xb),
              file=stderr)
        if gb != xb: raise TestFailureError()

        gs = str(i)
        print("bytes("+i.dump()+") => "+str(gs)+" exp "+str(xs),
              file=stderr)
        if gs != xs: raise TestFailureError()

        gd = i.dump()
        print(i.dump()+".dump() => "+str(gd)+" exp "+str(xd),
              file=stderr)
        if gd != xd: raise TestFailureError()
    print("ParseCtx_test2 completed ok", file=stderr)

def ParseCtx_test3():
    """Tests the following methods of bmisc.ParseCtx:
    __bool__, __len__, __iter__"""

    # Build a list of ParseCtx's to use as test input, out of other
    # tests' vectors.
    inputs = []
    for (i, x) in ParseCtx_tv1:
        if type(x) is tuple:
            inputs.append(bmisc.ParseCtx(*i))
    for t in ParseCtx_tv2:
        inputs.append(t[0])

    # See what bool(), len(), iter() give us for them, which correspond
    # to what bytes() does.
    for i in inputs:
        print("ParseCtx_test3() operating on: "+i.dump(), file=stderr)
        b = bytes(i)
        if len(b) != len(i):
            raise TestFailureError("len() mismatch", len(i), len(b))
        if bool(b) != bool(i):
            raise TestFailureError("bool() mismatch", len(i), len(b))
        bl = list(iter(b))
        il = list(iter(i))
        if bl != il:
            raise TestFailureError("iter() mismatch", il, bl)
        if len(i) > 0:
            raise TestFailureError("iter() left it non-empty")
    print("ParseCtx_test3 completed ok", file=stderr)

# XXX write ParseCtx testers for methods: get_byte(), get_bytes(), get_be2(), get_be4(), __getitem__()
