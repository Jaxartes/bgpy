# Jeremy Dilatush - All rights reserved.
# bgpy_misc.py - begun 27 April 2019
"Miscelleneous utility routines and classes used by bgpy."

import time, sys, socket

class TimeOfRecord(object):
    """Keeps track of the current time, for use in time stamps and
    scheduling and things like that.  Intentionally does *not* always
    update -- sometimes it's convenient for things, that are being
    done "about" the same time, to show exactly the same time stamp."""

    __slots__ = frozenset("t")
    def __init__(self):
        """Initialize the TimeOfRecord.  Initially it's in "free" mode."""
        self.t = None
    def get(self):
        """Retrieve the current time or time of record."""
        if self.t is None:
            # In "free" mode just return the current time
            return(time.time())
        else:
            return(self.t)
    def free(self):
        """Sets to "free" mode in which the current time is always used."""
        self.t = None
    def set(self):
        """Set the current time or time of record, to "right now."  Also
        returns it."""
        self.t = time.time()
        return(self.t)

tor = TimeOfRecord()

class FlagSet(object):
    """A set accessed as named attributes.  You can do foo.bar to check
    if "bar" is contained in "foo"; you can add and remove it; you don't
    have to worry about "bar" was ever defined as being in "foo"."""

    def __init__(self):
        pass
    def __getattr__(self, name):
        return(False)
    def __setattr__(self, name, value):
        if value:
            self.__dict__[name] = True
        elif name in self.__dict__:
            del self.__dict__[name]
    def __delattr__(self, name):
        if name in self.__dict__:
            del self.__dict__[name]
    def add(self, name):
        self.__dict__[name] = True

# dbg -- debugging flags, used in many places in the code
dbg = FlagSet()

def supersplit(s, end_at = None):
    """Split a string into a list of words (other strings), respecting
    quotes and backslashes."""

    words = []
    chars = []
    quotemode = False

    for (ch, lit) in superchars(s, append_chars=[(" ", False)]):
        if lit:
            # This character is taken literally
            chars.append(ch)
        elif quotemode:
            if ch == "\"":
                quotemode = False
            else:
                chars.append(ch)
        elif ch is end_at:
            if chars:
                words.append("".join(chars))
                chars = []
            break
        elif ch.isspace():
            if chars:
                words.append("".join(chars))
                chars = []
        elif ch == "\"":
            quotemode = True
        else:
            chars.append(ch)

    if quotemode:
        raise Exception("Unterminated quote")

    return(words)

superchar_singles = {
    'r': chr(13),
    'a': chr(7),
    'n': chr(10),
    't': chr(9),
    'b': chr(8),
    'f': chr(12)
}

def superchars(s, append_chars=[]):
    """Handle backslashes in a string, returning backslashed characters
    differently from the base characters themselves.  Used by supersplit().
    Yields 2-tuples: character, and a boolean indicating whether it's
    escaped somehow."""

    i = 0
    l = len(s)
    while i < l:
        if s[i] == "\\":
            i += 1
            if i >= l:
                raise Exception("dangling backslash")
            if s[i] in superchar_singles:
                yield(superchar_singles[s[i]], True)
                i += 1
            elif s[i] == "x":
                yield(chr(int(s[i+1:i+3], 16)), True)
                i += 3
            elif s[i] == "u":
                yield(chr(int(s[i+1:i+5], 16)), True)
                i += 5
            elif s[i] >= '0' and s[i] <= '9':
                yield(chr(int(s[i:i+3], 8)), True)
                i += 3
            else:
                yield (s[i], True)
                i += 1
        else:
            yield (s[i], False)
            i += 1
    for tuple in append_chars:
        yield(tuple)

def stamprint(msg):
    """Print a time stamped message 'msg'"""

    t = tor.get() # stamp it with the time of record
    ts = int(t)
    tu = round((t - ts) * 1e+6)
    print("{}.{:06d} {}".
            format(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
                   tu, msg), file=sys.stderr, flush=True)

class ConstantSet(object):
    """A set of constants which can be accessed as attributes easily.
    Also has ability to print informational names of them."""

    def __init__(self, *args, **kvattr):
        """Create a constant set with specified names and values;
        or with tuples of internal name, long name, value."""
        self._printable_names = dict()
        self._reverse = dict()
        for (k, pn, v) in args:
            self.__setattr__(k, v)
            self._printable_names[k] = pn
            self._reverse[v] = k
        for k in kvattr:
            self.__setattr__(k, kvattr[k])
            self._printable_names[k] = k
            self._reverse[kvattr[k]] = k

    def value2name(self, value):
        "reverse mapping -- value to short name"
        if value in self._reverse:
            return(self._reverse[value])
        else:
            return(repr(value))

    def value2printable_name(self, value):
        "reverse mapping -- value to printable name"
        if value in self._reverse:
            return(self._printable_names[self._reverse[value]])
        else:
            return(repr(value))

class ParseCtx(object):
    """Context information for use while parsing BGP messages in binary form.
    Includes:
        buf - the message being parsed; type "bytes"
        pos - current parse position in 'buf'
        end - parse position after the last one considered relevant
        as4 - whether 4 byte AS numbers are enabled."""

    __slots__ = ["buf", "pos", "end", "as4"]

    def __init__(self, obj, pos = None, end = None, as4 = None):
        """Constructor:
            ParseCtx(bytes)
                new context for whole of bytes
            ParseCtx(bytes, pos=X, end=X, as4=Y)
                fancier form: limited substring of bytes, 'as4' flag specified
            ParseCtx(ctx)
                copy of another context
        """

        # First, set up as if optional parameters aren't there
        if type(obj) is bytes:
            self.buf = obj
            self.pos = 0
            self.end = len(obj)
            self.as4 = False
        elif type(obj) is ParseCtx:
            self.buf = obj.buf
            self.pos = obj.pos
            self.end = obj.end
            self.as4 = obj.as4
        else:
            raise(TypeError("ParseCtx takes bytes or ParseCtx not "+
                            str(type(obj))))

        # Now, apply the optional parameters
        if end is not None:
            if type(end) is not int:
                raise(TypeError("end parameter for ParseCtx must be int"))
            elif end < 0 or self.pos + end > self.end:
                raise(IndexError("end value "+str(end)+" out of range"))
            else:
                self.end = self.pos + end
        if pos is not None:
            if type(pos) is not int:
                raise(TypeError("pos parameter for ParseCtx must be int"))
            elif pos < 0 or self.pos + pos > self.end:
                raise(IndexError("pos value "+str(pos)+" out of range"))
            else:
                self.pos += pos
        if as4 is not None:
            self.as4 = bool(as4)

    def __repr__(self):
        return("ParseCtx("+repr(self.buf[self.pos:self.end])+")")
    def __bytes__(self):
        return(self.buf[self.pos:self.end])
    def __bool__(self):
        return(self.end > self.pos)
    def __len__(self):
        return(self.end - self.pos)
    def __iter__(self):
        """Iterator which consumes the contents of the ParseCtx"""
        while self.pos < self.end:
            got = self.buf[self.pos]
            self.pos += 1
            yield got
    def get_byte(self):
        """Consume and return one byte, as an integer 0-255"""
        if self.pos < self.end:
            got = self.buf[self.pos]
            self.pos += 1
            return got
        else:
            raise KeyError("no more bytes")
    def get_bytes(self, count):
        """Consume and return some number of bytes, as new ParseCtx"""
        if self.pos + count > self.end:
            raise KeyError("not enough more bytes ("+str(count)+" requested)")
        else:
            got = ParseCtx(self, end = count)
            self.pos += count
            return got
    def get_be2(self):
        """Consume and return a two-byte big endian unsigned integer"""
        if self.pos + 2 > self.end:
            raise KeyError("not enough more bytes (2 requested)")
        else:
            got = (self.buf[self.pos] << 8) | self.buf[self.pos + 1]
            self.pos += 2
            return got
    def get_be4(self):
        """Consume and return a four-byte big endian unsigned integer"""
        if self.pos + 4 > self.end:
            raise KeyError("not enough more bytes (4 requested)")
        else:
            got = ((self.buf[self.pos    ] << 24) |
                   (self.buf[self.pos + 1] << 16) |
                   (self.buf[self.pos + 2] << 8 ) |
                   (self.buf[self.pos + 3]      ))
            self.pos += 4
            return got
    def dump(self):
        """Dump internal structure of ParseCtx, for debugging."""
        return("ParseCtx{"+str(self.buf)+
               "["+str(self.pos)+":"+str(self.end)+"],as4="+
               str(self.as4)+"}")
    def _reindex(self, idx, fix = False):
        """Convert an index to go within self.buf"""
        if type(idx) is not int:
            raise TypeError("ParseCtx indices must be integers")
        elif self.pos + idx >= self.end:
            if fix:
                return(self.end)
            else:
                raise IndexError("ParseCtx index out of range")
        elif idx >= 0:
            return(self.pos + idx)
        elif self.end + idx < self.pos:
            if fix:
                return(self.pos)
            else:
                raise IndexError("ParseCtx index out of range")
        else:
            return(self.end + idx)
    def __getitem__(self, key):
        """get byte at index or slice"""
        if type(key) is slice:
            if key.step is not None:
                # Not implementing this, it wouldn't make sense to use.
                raise TypeError("ParseCtx doesn't do extended slicing")
            else:
                if key.start is None:
                    start = self.pos
                else:
                    start = self._reindex(key.start, True)
                if key.stop is None:
                    stop = self.end
                else:
                    stop = self._reindex(key.stop, True)
                return(self.buf[start:stop])
            # This code is a little inconsistent with other
            # implementations in the slice case; it won't tolerate
            # "stop" being out of range.  But that's probably not too
            # important for the limited uses ParseCtx() will be put to.
        else:
            # single index
            return(self.buf[self._reindex(key)])
    # XXX I'm not sure I'm going to use the 'as4' flag here, if I don't in the end, maybe get rid of it
    def __eq__(self, other): return(bytes(self) == bytes(other))
    def __ne__(self, other): return(bytes(self) != bytes(other))
    def __lt__(self, other): return(bytes(self) <  bytes(other))
    def __gt__(self, other): return(bytes(self) >  bytes(other))
    def __le__(self, other): return(bytes(self) <= bytes(other))
    def __ge__(self, other): return(bytes(self) >= bytes(other))

def ba_put_be2(ba, x):
    """Append a 2 byte big endian unsigned integer to a bytearray"""
    if x < 0 or x > 65535:
        raise ValueError("value must be a 16 bit unsigned integer")
    ba.append(x >> 8)
    ba.append(x & 255)

def ba_put_be4(ba, x):
    """Append a 4 byte big endian unsigned integer to a bytearray"""
    if x < 0 or x > 4294967295:
        raise ValueError("value must be a 32 bit unsigned integer")
    ba.append(x >> 24)
    ba.append((x >> 16) & 255)
    ba.append((x >> 8) & 255)
    ba.append(x & 255)

def single_instance(cls):
    """Decorator to replace a class definition with a single instance of
    that class.  Example:
        @single_instance
        class thingy(object):
            def __init__(self): pass
            def __str__(self): return("Thingy")
    """
    return(cls())

class ChoosableRange(object):
    """A set, possibly huge, of strings, which can be specified in terms
    of a ranges and collections of values.  To use:
        create with range notation
        use len() to find out the total size of the set
        use choice() (in 'random') to select members pseudorandomly
    """

    # internal structure:
    #   hex - True if t = "hex", False if t = "dec"
    #   parts - list with one entry per part of the range specification;
    #       each is one of the following:
    #           fixed value string
    #           2-tuple containing min & count integers of a decimal range
    #           3-tuple containing min & count integers of a hex range, & length
    #   count - number of elements
    __slots__ = frozenset(["hex", "parts", "count"])

    def __init__(self, spec, t = "dec",
                 prefix = "(", infix = "-", suffix = ")"):
        """Build the set using range notation.  Example:
        "1.(2-3).(4-6).0/24", which has 6 elements.  The ranges can be
        of decimal integers (the default) or fixed length hexadecimal
        integers (with t = "hex")."""

        if t == "dec":      self.hex = False
        elif t == "hex":    self.hex = True
        else:               raise ValueError("unknown 't' value")

        # start out with a range containing just empty string, then
        # parse 'spec' and fill it out
        self.parts = []
        self.count = 1
        pos = 0
        while pos < len(spec):
            # look for "("
            pp = spec.find(prefix, pos)
            if pp < 0: pp = len(spec)
            if pp > pos:
                # there's some constant stuff
                self.parts.append(spec[pos:pp])
                pos = pp
            else:
                # there's a range; look for "-" and ")"
                ip = spec.find(infix, pos)
                sp = spec.find(suffix, pos)
                if sp < 0: raise ValueError("'(' without ')'")
                if ip < 0 or ip > sp: raise ValueError("'( )' without '-'")
                p1 = spec[(pos+len(prefix)):ip]
                p2 = spec[(ip+len(infix)):sp]
                pos = sp + len(suffix)

                # Now that we have the range endpoints as strings (p1 & p2),
                # check them and convert them to numbers.
                if self.hex:
                    # p1 & p2 should be two hex strings of the same length
                    l = len(p1)
                    if l != len(p2):
                        raise ValueError("length mismatch in hex range")
                    for p in (p1, p2):
                        if len(p) == 0:
                            raise ValueError("empty string in range")
                        for d in p:
                            if d >= '0' and d <= '9':
                                pass # ok, it's a hex digit
                            elif d >= 'a' and d <= 'f':
                                pass # ok, it's a hex digit
                            elif d >= 'A' and d <= 'F':
                                pass # ok, it's a hex digit
                            else:
                                raise ValueError("non hex digit in hex range")
                    p1 = int(p1, 16)
                    p2 = int(p2, 16)
                    if p2 < p1:
                        raise ValueError("hex range out of order")
                    self.parts.append((p1, p2 - p1 + 1, l))
                else:
                    # p1 & p2 should be two decimal integers
                    for p in (p1, p2):
                        if len(p) == 0:
                            raise ValueError("empty string in range")
                        for d in p:
                            if d >= '0' and d <= '9':
                                pass # ok, it's a digit
                            else:
                                raise ValueError("non digit in range")
                    p1 = int(p1, 10)
                    p2 = int(p2, 10)
                    if p2 < p1:
                        raise ValueError("range out of order")
                    self.parts.append((p1, p2 - p1 + 1))
                self.count *= p2 - p1 + 1

    def __len__(self):
        return(self.count)

    def __getitem__(self, key):
        if type(key) is not int:
            raise TypeError("ChoosableRange() index should be 'int'")
        if key < 0:
            raise IndexError("ChoosableRange() index should not be negative")
        res = ""
        for p in self.parts:
            if type(p) is str:
                # constant string
                res += p
            elif self.hex:
                # hexadecimal range
                key0 = key % p[1]
                key //= p[1]
                res += "{:0{width}x}".format(p[0] + key0, width = p[2])
            else:
                # decimal range
                key0 = key % p[1]
                key //= p[1]
                res += str(p[0] + key0)

        if key > 0:
            raise IndexError("ChoosableRange() index too high")

        return(res)

class ChoosableConcat(object):
    """A combination of ChoosableRange()s.
    This is a concatenation, not a union, if you care."""

    __slots__ = frozenset(["subs", "cumul"])

    def __init__(self, subs = []):
        self.subs = []
        self.cumul = []
        for sub in subs: self.add(sub)

    def add(self, sub):
        self.subs.append(sub)
        l = len(sub)
        if len(self.cumul): l += self.cumul[-1]
        self.cumul.append(l)

    def __len__(self):
        if len(self.cumul):
            return(self.cumul[-1])
        else:
            return(0)

    def __getitem__(self, key):
        if type(key) is not int:
            raise TypeError("ChoosableConcat() index should be 'int'")
        if key < 0:
            raise IndexError("ChoosableConcat() index should not be negative")
        if len(self.subs) == 0:
            # since it's empty, every 'key' value is out of range
            raise IndexError("ChoosableConcat() is empty")
        if key >= self.cumul[-1]:
            raise IndexError("ChoosableConcat() index is too high")
        
        # binary search among the ranges
        mn = 0                      # minimum index in the range
        mx = len(self.cumul) - 1    # maximum index in the range

        while mx > mn:
            # pick a midpoint for the range, and look at it
            md = (mn + mx) >> 1
            if key < self.cumul[md]:
                # key falls somewhere in mn ... md
                mx = md
            else:
                # key falls somewhere in md + 1 ... mx
                mn = md + 1

        # and do lookup in that range
        if mn > 0: key -= self.cumul[mn - 1]
        return(self.subs[mn][key])

class EqualParms(object):
    """Handle name=value parameters.  You create an EqualParms object with
    the appropriate information, then you can use it to parse the parameters
    and validate them.  Usage:
        create one, empty
        add known names with add*()
        parse input with parse()"""

    def __init__(self):
        """Initializes it, empty."""
        self.seen = set() # all names seen
        self.aliases = dict() # maps alias names to canonical names
        self.descs = dict() # descriptive strings of each
        self.parsers = dict() # parse each parameter value from string
        self.values = dict() # values parsed if any
        self.storers = dict() # callbacks to store results

    def add_alias(self, name, cname):
        """Define an alias, named 'name', pointing to 'cname'."""
        if name in self.seen: raise KeyError("Name redefined")
        if cname not in self.seen:
            raise KeyError("Dangling alias")
        self.seen.add(name);
        self.aliases[name] = cname

    def add(self, name, desc, parser = None, storer = None):
        """Define a name 'name'.  'desc' is its description.
        'parser' is a function to call to parse it (passed this EqualParms;
        the name; the previous value or None; and the string to parse).
        'storer' is used to store it,
        and may be omitted to just use 'self.values'."""

        if name in self.seen: raise KeyError("Name redefined")
        self.seen.add(name)
        self.descs[name] = desc
        if parser is not None: self.parsers[name] = parser
        if storer is not None: self.storers[name] = storer

    def describe(self):
        "Iterate over names known, with descriptions, for help purposes."

        for name in sorted(self.seen):
            if name in self.descs:
                desc = self.descs[name]
            elif name in self.aliases:
                desc = "synonym for \"" + self.aliases[name] + "\""
            else:
                desc = "(no information)"
            yield((name, desc))

    def parse(self, arg):
        "Parse a name=value pair from string."
        try:
            (n, v) = arg.split("=", 1)
        except:
            n = None
            v = arg
        if n not in self.seen:
            if n is None:
                raise Exception("expected name=value pair not \""+arg+"\"")
            else:
                raise Exception("unrecognized name \"" + n +
                                "\" in name=value pair")
        while n in self.aliases:
            n = self.aliases[n]
        if n in self.values:
            pv = self.values[n]
        else:
            pv = None
        if n in self.parsers:
            v2 = self.parsers[n](self, n, pv, v)
        else:
            v2 = v
        self.values[n] = v2
        if n in self.storers:
            self.storers[n](v2)

    def __getitem__(self, n):
        "Look up the value last parsed for name 'n'."
        while n in self.aliases:
            n = self.aliases[n]
        return(self.values[n])

    def __setitem__(self, n, v):
        "Set the value for name 'n' bypassing the parser."
        while n in self.aliases:
            n = self.aliases[n]
        self.values[n] = v

def EqualParms_parse_i32(ep, n, pv, s):
    """'parser' routine for EqualParms() to parse a 32-bit unsigned
    integer."""

    try:
        x = int(s)
        if x < 0 or x > 4294967295:
            raise Exception()
        return(x)
    except:
        pass
    raise Exception(n+" must be integer in 0-4294967295 range")

def EqualParms_parse_i32_ip(ep, n, pv, s):
    """'parser' routine for EqualParms() to parse a 32-bit unsigned integer
    possibly in IPv4 address format."""

    try:
        return(EqualParms_parse_i32(ep, n, pv, s))
    except: pass
    try:
        bs = socket.inet_aton(s)
            # Apparently, socket.inet_aton() tolerates some things I wouldn't
            # expect it to.  Ah well.
        x = 0
        for b in bs:
            x = (x << 8) + b
        return(x)
    except: pass
    raise Exception(n+" must be either an IPv4 address in dotted"+
                    " quad format, or an integer in 0-4294967295 range.")
