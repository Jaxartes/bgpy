# Jeremy Dilatush - All rights reserved.
# bgpy_misc.py - begun 27 April 2019
"Miscelleneous utility routines and classes used by bgpy."

## ## ## Top matter

import socket
import sys
import time

## ## ## Functions

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
            if i < l:
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
                yield(chr(int(s[i+1:i+4], 8)), True)
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
            format(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tu)),
                   tu, msg), file=fp)

class constant_set(object):
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

    # XXX add method for getting printable name and for reverse lookup
