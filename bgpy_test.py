# bgpy_test.py - begun 4 May 2019
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
"""Tests for code in bgpy.  How much I write of this is uncertain.  I generally
prefer testing code "in use" rather than piece by piece (the proof of the
pudding is in the eating).  In the case of bgpy, operating sanely and as
intended when connected to a real BGP implementation is the goal."""

# XXX there's a lot this code doesn't test

## ## ## Top matter

from sys import stderr
import bgpy_misc as bmisc
import random

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
    ParseCtx_test4()
    ParseCtx_test5()
    print("ParseCtx_test completed ok", file=stderr)

# test vector for ParseCtx_test1(): input to constructor; expected
# exception / buf, pos, end, as4 values
ParseCtx_tv1 = [
    ((b"one",),
     (b"one", 0, 3)),
    ((bmisc.ParseCtx(b"two"),),
     (b"two", 0, 3)),
    ((bmisc.ParseCtx(b"three", 1, 3),),
     (b"three", 1, 3)),
    ((b"four", 2, 2),
     (b"four", 2, 2)),
    ((None,),
     TypeError),
    ((bmisc.ParseCtx(b"five-six", 2, 4), None, 1),
     (b"five-six", 2, 3)),
    ((bmisc.ParseCtx(b"seven-eight", 3, 8), 1, None),
     (b"seven-eight", 4, 8)),
    ((bmisc.ParseCtx(b"nine-ten", 2), 1.5),
     TypeError),
    ((bmisc.ParseCtx(b"nine-ten", 2), None, 1.5),
     TypeError),
    ((bmisc.ParseCtx(b"nine-ten", 2), 2, 3),
     (b"nine-ten", 4, 5)),
    ((bmisc.ParseCtx(b"nine-ten", 2), 2, 2),
     (b"nine-ten", 4, 4)),
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
            g = (gg.buf, gg.pos, gg.end)
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
     "ParseCtx(b'')", b"", "ParseCtx{b''[0:0]}"),
    (bmisc.ParseCtx(b"xyz", 1),
     "ParseCtx(b'yz')", b"yz", "ParseCtx{b'xyz'[1:3]}"),
    (bmisc.ParseCtx(b"alpha", 0, 3),
     "ParseCtx(b'alp')", b"alp", "ParseCtx{b'alpha'[0:3]}"),
    (bmisc.ParseCtx(b"beta", 1, 1),
     "ParseCtx(b'')", b"", "ParseCtx{b'beta'[1:1]}"),
]

def ParseCtx_test2():
    """Tests the following methods of bmisc.ParseCtx:
    __repr__, __bytes__, dump, and the nonexistent __str__"""

    for (i, xr, xb, xd) in ParseCtx_tv2:
        i = bmisc.ParseCtx(i)
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
        inputs.append(bmisc.ParseCtx(t[0]))

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

def ParseCtx_test4():
    """Tests the following methods of bmisc.ParseCtx:
    get_byte(), get_bytes(), get_be2(), get_be4()"""

    # Test vector: parallel lists of byte values, how to try reading them,
    # and what to expect to get.
    tv = [
        ([97], "get_byte", (), 97),
        ([98, 99], "get_bytes", (2,), b"bc"),
        ([100, 101], "get_be2", (), 25701),
        ([102, 103, 104], "get_bytes", (3,), b"fgh"),
        ([], "get_bytes", (0,), b""),
        ([7, 250], "get_be2", (), 2042),
        ([250, 7], "get_be2", (), 64007),
        ([1, 3, 5, 7], "get_be4", (), 16975111),
        ([200, 100, 50, 25], "get_be4", (), 3362009625),
        ([0], "get_byte", (), 0),
        ([0, 0, 0, 0, 0], "get_bytes", (5,), b"\000\000\000\000\000"),
        ([], "get_bytes", (0,), b""),
        ([1, 1, 0, 255, 1], "get_bytes", (5,), b"\001\001\000\377\001"),
        ([254, 0], "get_be2", (), 65024),
        ([0, 254], "get_be2", (), 254),
        ([0, 0], "get_be2", (), 0),
        ([0, 0, 0, 0], "get_be4", (), 0),
        ([0, 0, 253, 252], "get_be4", (), 65020),
        ([0, 251, 0, 250], "get_be4", (), 16449786),
        ([0, 249, 248, 0], "get_be4", (), 16381952),
        ([247, 0, 0, 246], "get_be4", (), 4143972598),
        ([245, 0, 244, 0], "get_be4", (), 4110480384),
        ([243, 242, 0, 0], "get_be4", (), 4092723200)
    ]

    # Build the ParseCtx out of all the lists of bytes
    bs = []
    for t in tv: bs += t[0]
    pc = bmisc.ParseCtx(bytes(bs))

    print("ParseCtx_test4() test input:", file=stderr)
    print("    "+pc.dump(), file=stderr)

    # Go through the parsing
    for t in tv:
        fn = t[1]
        fa = t[2]
        x = t[3]
        g = eval("bmisc.ParseCtx."+fn)(pc, *fa)
        print("pc."+fn+str(fa)+" => "+repr(g)+" exp "+repr(x), file=stderr)
        if type(g) is bytes: raise TestFailureError("got bytes")
        if type(g) is bmisc.ParseCtx: g = bytes(g)
        if g != x: raise TestFailureError(g = g, e = x)

    # Now the ParseCtx should be empty.  Check that.  One might expect
    # to also test that get_*() all handle an empty/exhausted ParseCtx()
    # properly, with exceptions; but ParseCtx() isn't really meant to
    # be used that way.
    if len(pc):
        raise TestFailureError("pc is not empty at end")

    print("ParseCtx_test4 completed ok", file=stderr)

def ParseCtx_test5():
    """Test bmisc.ParseCtx.__getitem__()"""

    # a ParseCtx to use for testing; and the bytes it contains
    pc = bmisc.ParseCtx(b"This is a test. This is only a test."+
                        b" What else would it be?")
    if len(pc) != 59: raise Error("internal error")
    pc = bmisc.ParseCtx(pc, pos = 3, end = 54)
    bs = bytes(pc)

    # a bunch of indexes/slices to try
    ixs = []
    for i in range(-60, 60, 5): ixs.append(i)
    ixs.append(None) # intentionally bogus
    ixs.append(1.5)  # intentionally bogus
    for i in range(-63, 63, 7):
        for j in range(-64, 64, 8):
            ixs.append(slice(i, j))

    # try those indexes/slices to see if they get the same results for
    # pc & bs (ParseCtx & bytes)
    for i in ixs:
        # collect results
        try:
            g = [False, pc[i]]
            if type(i) is slice: g[1] = bytes(g[1])
        except Exception as e: g = [True, e]
        try: x = [False, bs[i]]
        except Exception as e: x = [True, e]

        # and results as appropriate to comparison
        for l in [g, x]:
            if l[0]:
                # an exception, only compare the type, not the text
                l.append(type(l[1]))
            else:
                # a result, compare exactly
                l.append(l[1])

        # report & check
        print("index "+repr(i)+": got "+repr(g[1])+" exp "+repr(x[1]),
              file=stderr)
        if g[2] != x[2]:
            raise TestFailureError()

    print("ParseCtx_test5 completed ok", file=stderr)

def ChoosableConcat_test():
    """Test bmisc.ChoosableRange & bmisc.ChoosableConcat."""

    # test vector
    tv = [
        ([], []),
        ([("1", "dec")], ["1"]),
        ([("1", "hex")], ["1"]),
        ([("(2-3)", "dec")], ["2", "3"]),
        ([("(4-5)(7-10)", "dec")],
         ["47", "48", "49", "410", "57", "58", "59", "510"]),
        ([("-(11-12)-(1f-21)-", "hex")],
         ["-11-1f-", "-11-20-", "-11-21-",
          "-12-1f-", "-12-20-", "-12-21-"]),
        ([("13/(18-20)/16", "dec"),
          ("13/x(18-20)/16", "hex")],
         ["13/18/16", "13/19/16", "13/20/16",
          "13/x18/16", "13/x19/16", "13/x1a/16", "13/x1b/16",
          "13/x1c/16", "13/x1d/16", "13/x1e/16", "13/x1f/16",
          "13/x20/16"]),
        (list(map(lambda i: (i, "dec"), ["1", "(2-3)", "4", "(5-7)",
                                         "8", "(9-10)", "(11-13)", "1(4-4)"])),
         list(map(str, range(1, 15))))
    ]

    for ins, exp in tv:
        le = len(exp)
        exp = set(exp)
        subs = []
        inrep = []
        for spec, t in ins:
            subs.append(bmisc.ChoosableRange(spec, t = t))
        cc = bmisc.ChoosableConcat(subs)
        lg = len(cc)
        got = set(cc)
        print(repr((ins, exp)) + ": ", file=stderr)
        print("\tgot len: " + repr(lg), file=stderr)
        print("\texp len: " + repr(le), file=stderr)
        if lg != le: raise TestFailureError()
        print("\tgot val: " + repr(got), file=stderr)
        print("\texp val: " + repr(exp), file=stderr)
        if got != exp: raise TestFailureError()

    print("ChoosableConcat_test completed ok", file=stderr)

def parse_ipv6_test():
    """Test bmisc.parse_ipv6()."""

    # test vector: cases that should succeed
    tv = [
        ("::", [0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0]),
        ("1::", [0, 1, 0, 0, 0,0,0,0, 0,0,0,0, 0,0,0,0]),
        ("::1", [0,0,0,0, 0,0,0,0, 0,0,0,0, 0, 0, 0, 1]),
        ("aaa::bbb", [10, 170, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 11, 187]),
        ("1234:5::", [18, 52, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        ("::678:9a", [0,0,0,0, 0,0,0,0, 0,0,0,0, 6, 120, 0, 154]),
        ("b:c:d::", [0, 11, 0, 12, 0, 13, 0, 0, 0,0,0,0, 0,0,0,0]),
        ("::e:f:0", [0,0,0,0, 0,0,0,0, 0, 0, 0, 14, 0, 15, 0, 0]),
        ("1248:36cb::5a7e:fd91",
         [18, 72, 54, 203, 0,0,0,0, 0,0,0,0, 90, 126, 253, 145]),
        ("1:1:1:1:1::1:1",
         [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1]),
        ("1:1:1::1:1:1:1:1",
         [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]),
        ("1:2:3:4:5:6:7:8",
         [0, 1, 0, 2, 0, 3, 0, 4, 0, 5, 0, 6, 0, 7, 0, 8]),
        ("1:ffff:0:0:eeee::",
         [0, 1, 255, 255, 0, 0, 0, 0, 238, 238, 0, 0, 0,0,0,0])
    ]
    if False: tv[3:3] = [(":::::", [])]     # enable to test the test
    if False: tv[5:5] = [("::", [0] * 17)]  # enable to test the test

    # test vector: cases that should fail (won't check the error message
    # just the factor of their failure)
    tv2 = [
        "", ":", ":::", "::::", "1:2:3:4:5:6:7", "1:2:3:4:5:6:7:8:9",
        "1:2::3:4::5:6", "ffff::10000", "ffff::-1", "10000::ffff",
        "-1::ffff", "1:2:3:g:4:5:6:7"
    ]

    # do the positive tests
    for tin, tex in tv:
        print("input "+repr(tin)+":", file=stderr)
        tou = list(bmisc.parse_ipv6(tin))
        print("\texp: "+repr(tex), file=stderr)
        print("\tgot: "+repr(tou), file=stderr)
        if tex != tou:
            raise TestFailureError()

    # do the negative tests
    for tin in tv2:
        print("input "+repr(tin)+":")
        try:
            tou = list(bmisc.parse_ipv6(tin))
            gotf = False
            got = repr(tou)
        except Exception as e:
            gotf = True
            got = "failure: "+str(e)
        print("\texp: failure", file=stderr)
        print("\tgot: "+got, file=stderr)
        if not gotf:
            raise TestFailureError()

    print("parse_ipv6_test completed ok", file=stderr)

def Partition_test(count = 3, size = 10, seed = 123, verbose = False):
    """Test bmisc.Partition()."""

    prng = random.Random(seed)

    sets  = [] # list of lists of values to use in test
    parts = [] # list of 'count' Partition() objects, each on its set
    shads = [] # list of "shadows", containing the same information as
               # a Partition object, in the form of a dict() mapping each
               # value to the set of values in its part

    print("Picking "+str(count)+" sets of "+str(size)+" integers", file=stderr)
    for i in range(count):
        sets.append([])
        in_this_set = set()
        while len(sets[i]) < size:
            n = prng.randrange(0, 2 * size)
            if n in in_this_set:
                continue
            in_this_set.add(n)
            sets[i].append(n)
        if verbose:
            print("\tsets["+str(i)+"] = "+repr(sets[i]), file=stderr)

    print("Building Partition()s and their shadows", file=stderr)
    for i in range(count):
        parts.append(bmisc.Partition(sets[i]))
        shads.append(dict())
        for v in sets[i]:
            shads[i][v] = {v}

    nops = prng.randrange(0, int(count * size * 1.25 + 2))
    print("Performing "+str(nops)+" joins", file=stderr)
    while nops > 0:
        nops -= 1
        i = prng.randrange(0, count)
        v1 = prng.choice(sets[i])
        v2 = prng.choice(sets[i])
        if verbose:
            print("\tparts["+str(i)+"].sub_join("+str(v1)+", "+str(v2)+")",
                  file=stderr)
        parts[i].sub_join(v1, v2)
        u = shads[i][v1].union(shads[i][v2])
        for v in u:
            shads[i][v] = u

    print("Checking resulting partition contents", file=stderr)
    for i in range(count):
        for v1 in sets[i]:
            for v2 in sets[i]:
                ss = parts[i].sub_same(v1, v2)
                tt = v1 in shads[i][v2]
                if ss != tt:
                    print("ERROR!\n"+
                          "parts["+str(i)+"].sub_same("+repr((v1, v2))+") ==> "+
                          str(ss)+"\n" +
                          str(v1)+" in shads["+str(i)+"]["+str(v2)+"] ==> "+
                          str(tt), file=stderr)
                    raise TestFailureError()
        if verbose:
            print("parts["+str(i)+"] matches shads["+str(i)+"]", file=stderr)

    print("Partition_test completed ok", file=stderr)

def mask_check_test(count=1000, seed=1, verbose=False):
    """Test bmisc.mask_check()."""

    prng = random.Random(seed)

    bits32 = 2**32 - 1

    targets = ([(True, False)] * 10 + [(False, True)] * 10 +
               [(True, True)] * 4 + [(False, False)])

    for i in range(count):
        # figure out target result
        tlft, trgt = prng.choice(targets)
        # pick a masklength
        ml = prng.randint(0, 31)
        # pick an address (as a number) & mask it as desired
        full = prng.randint(0, bits32)
        alft = full & (bits32 - (bits32 >> ml))
        argt = full & (bits32 >> ml)
        anum = 0
        if not tlft: alft = 0
        if not trgt: argt = 0
        anum |= alft
        anum |= argt
        elft = (alft != 0)
        ergt = (argt != 0)
        # convert it into a list of byte values
        addr = []
        for j in range(24, -1, -8):
            addr.append(255 & (anum >> j))
        # perform the test:
        glft, grgt = bmisc.mask_check(bytes(addr), ml)
        if glft != elft or grgt != ergt or verbose:
            print(str(i) + ": bmisc.mask_check" + repr((addr, ml)) +
                  " ==> " + repr((glft, grgt)), file=stderr)
        if glft != elft or grgt != ergt:
            print("MISMATCH!", file=stderr)
            raise TestFailureError()

    print("make_check_test completed ok", file=stderr)
