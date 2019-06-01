# Jeremy Dilatush - All rights reserved.
# bgpy_misc.py - begun 27 April 2019
"Miscelleneous utility routines and classes used by bgpy."

import time

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

def stamprint(fp, t, msg):
    """Print a time stamped message, to file fp, for time t, with message msg"""

    ts = int(t)
    tu = round((t - ts) * 1e+6)
    print("{}.{:06d} {}".
            format(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
                   tu, msg), file=fp)

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
