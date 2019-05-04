# Jeremy Dilatush - All rights reserved.
# bgpy_test.py - begun 4 May 2019
"""Tests for code in bgpy.  How much I write of this is uncertain.  I generally
prefer testing code "in use" rather than piece by piece (the proof of the
pudding is in the eating).  In the case of bgpy, operating sanely and as
intended when connected to a real BGP implementation is the goal."""

## ## ## Top matter

import sys
import time
import bgpy_misc as bmisc

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
        print("bmisc.supersplit"+str(i)+" expecting "+str(x), file=sys.stderr)
        g = bmisc.supersplit(*i)
        if g != x:
            print("got: "+str(g), file=sys.stderr)
            raise Error("Mismatch, test failed")
    print("supersplit_test completed ok", file=sys.stderr)

## ## ## test bmisc.ConstantSet()

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
        print("cs."+xsn+" => "+str(v)+" exp "+str(xv), file=sys.stderr)
        if v != xv: raise Error("Mismatch, test failed")
        gsn = cs.value2name(xv)
        print("cs.value2name("+str(xv)+") => "+str(gsn)+ " exp "+str(xsn),
              file=sys.stderr)
        if gsn != xsn: raise Error("Mismatch, test failed")
        gpn = cs.value2printable_name(xv)
        print("cs.value2printable_name("+str(xv)+") => "+str(gpn)+
              " exp "+str(xpn), file=sys.stderr)
        if gpn != xpn: raise Error("Mismatch, test failed")
    print("ConstantSet_test completed ok", file=sys.stderr)

## ## ## test bmisc.ParseCtx()

def ParseCtx_test():
    # XXX todo
