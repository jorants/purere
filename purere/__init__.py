from . import compiler
from . import topy
from . import constants
import sre_parse

# Used for groupindex to make it non-modifiable
try:
    from types import MappingProxyType
except ImportError:

    class MappingProxyType(dict):
        def __setattr__(self, *args):
            raise TypeError("Not alowed to change")


__version__ = "0.0.1"


class Match:
    def __init__(self, pattern_info, arg_info, regs):
        self._pattern_info = pattern_info
        self._arg_info = arg_info
        self.regs = regs

        self._groupindex = self._pattern_info["groupindex"]

        self.string = arg_info["string"]

        self.pos, self.endpos = arg_info["pos"], arg_info["endpos"]
        self.span = lambda group=0: regs[group]
        self.start, self.end = (
            lambda group=0: regs[group][0],
            lambda group=0: regs[group][1],
        )
        self.re = pattern_info["pattern"]
        self._basetype = pattern_info["basetype"]
        try:
            lastmark, self.lastindex = max(
                (max(reg), -i - 1) for i, reg in enumerate(self.regs[1:])
            )
            self.lastindex *= -1
            if lastmark == -1:
                self.lastindex = None
        except ValueError as e:
            self.lastindex = None
        self.lastgroup = None
        if self.lastindex and self.lastindex in self._groupindex.values():
            self.lastgroup = next(
                key
                for key, value in self._groupindex.items()
                if value == self.lastindex
            )

    def group(self, *groups, default=None):
        if not groups:
            groups = [0]
        try:
            groups = [self._groupindex[g] if isinstance(g, str) else g for g in groups]
        except KeyError as e:
            raise IndexError("no such group")
        try:
            groups = [i.__index__() for i in groups]
        except AttributeError:
            raise IndexError("no such group")
        for i in groups:
            if i < 0 or i >= len(self.regs):
                raise IndexError("no such group")
        res = tuple(
            [
                self._basetype(self.string[slice(*self.regs[group])])
                if self.regs[group][0] != -1
                else default
                for group in groups
            ]
        )

        return res if len(res) > 1 else res[0]

    def groups(self, default=None):
        return tuple(
            self._basetype(self.string[slice(*reg)]) if reg[0] != -1 else default
            for reg in self.regs[1:]
        )

    def groupdict(self, default=None):
        names = self._groupindex.keys()
        values = self.group(*names, default=default)
        return {k: v for k, v in zip(names, values)}

    def _expand(self, comprepl):
        mapping, parts = comprepl
        mapping = dict(mapping)
        res = []
        for i, part in enumerate(parts):
            if part != None:
                res.append(part)
            else:
                groupnum = mapping[i]
                res.append(self.group(groupnum, default=""))
        return res

    def expand(self, repl):
        comprepl = _compile_repl(repl, self.re)
        return self._basetype().join(self._expand(comprepl))

    def __getitem__(self, g):
        return self.group(g)

    def _findall_out(self):
        if len(self.regs) == 1:
            return self.group(0, default="")
        else:
            return self.group(*range(1, len(self.regs)), default="")

    def __repr__(self):
        return f"<purere.Match object; span={repr(self.span())}, match={repr(self.group(0))}>"


class _Scanner:
    def __init__(self, pattern, string, pos=0, endpos=None):
        self._pos = pos
        self._curpos = pos
        self._last_empty = False
        self.pattern = pattern
        self._string = string
        self._done = False
        self._endpos = endpos

    def _run(self, f):
        if self._done:
            return
        res = f(
            self._string, self._curpos, self._endpos, nonempty_first=self._last_empty
        )
        if res:
            # fix starting position
            res.pos = self._pos
            span = res.span()
            self._curpos = span[1]
            self._last_empty = span[0] == span[1]
            return res
        else:
            self._done = True
            self._curpos = len(self._string)
            return

    def match(self):
        return self._run(self.pattern._match)

    def search(self):
        return self._run(self.pattern._search)


class Pattern:
    def __init__(self, pattern, flags=0):
        self.pattern = pattern
        if not isinstance(flags, RegexFlag):
            flags = RegexFlag(flags)
        self._info, self._match_function = compiler.compile_regex(pattern, flags=flags)
        self.flags = self._info["flags"]
        self.groups = self._info["groups"] - 1
        self.groupindex = MappingProxyType(self._info["groupdict"])
        self._basetype = str if isinstance(self.pattern, str) else bytes
        self.pattern_info = {
            "pattern": self,
            "groups": self.groups,
            "groupindex": self.groupindex,
            "basetype": self._basetype,
        }

    def _check_type(self, s):
        if self.flags & BYTEPATTERN and isinstance(s, str):
            raise TypeError("Can only match byte-like types with byte pattern")
        elif not (self.flags & BYTEPATTERN) and not isinstance(s, str):
            raise TypeError("Can only match str types with string pattern")

    def _match(self, string, pos=0, endpos=None, nonempty=False, full=False):
        success, ending, marks = self._match_function(
            string, pos=pos, endpos=endpos, nonempty=nonempty, full=full
        )
        if success:
            arg_info = {
                "string": string,
                "pos": pos,
                "endpos": endpos if endpos != None else len(string),
            }
            regs = tuple(
                [(pos, ending)]
                + [(marks[i], marks[i + 1]) for i in range(0, len(marks), 2)]
            )
            regs = tuple((a, b) if a != None else (-1, -1) for a, b in regs)
            return Match(self.pattern_info, arg_info, regs)
        else:
            return None

    def _search(self, string, pos=0, endpos=None, nonempty_first=False):
        if not endpos:
            endpos = len(string)
        minlen = self._info["min"]

        for i in range(pos, endpos + 1 - minlen):
            if self._info["prefix_checker"] and not self._info["prefix_checker"](
                string, i
            ):
                continue

            match = self._match(
                string, pos=i, endpos=endpos, nonempty=nonempty_first and i == pos
            )
            if match:
                match.pos = pos
                return match
        return None

    def search(self, string, pos=0, endpos=None):
        self._check_type(string)
        return self._search(string, pos=pos, endpos=endpos)

    def match(self, string, pos=0, endpos=None):
        self._check_type(string)
        return self._match(string, pos=pos, endpos=endpos)

    def fullmatch(self, string, pos=0, endpos=None):
        self._check_type(string)
        return self._match(string, pos=pos, endpos=endpos, full=True)

    def findall(self, string, pos=0, endpos=None):
        self._check_type(string)
        res = [match._findall_out() for match in self.finditer(string, pos, endpos)]
        return res

    def finditer(self, string, pos=0, endpos=None):
        self._check_type(string)
        s = self.scanner(string, pos=pos, endpos=endpos)

        while True:
            res = s.search()
            if res == None:
                return
            else:
                yield res

    def split(self, string, maxsplit=0):
        self._check_type(string)
        parts = []
        if maxsplit > 0:
            iterator = zip(range(maxsplit), self.finditer(string))
        else:
            iterator = zip(range(2 * len(string)), self.finditer(string))
        position = 0
        for i, match in iterator:
            parts.append(self._basetype(string[position : match.start()]))
            position = match.end()
            parts += match.groups()
        parts.append(self._basetype(string[position:]))
        return parts

    def scanner(self, string, pos=0, endpos=None):
        self._check_type(string)
        return _Scanner(self, string, pos=pos, endpos=endpos)

    def sub(self, repl, string, count=0):
        return self.subn(repl, string, count=count)[0]

    def subn(self, repl, string, count=0):
        self._check_type(string)
        if callable(repl):
            replf = lambda x: [repl(x)]
        else:
            self._check_type(repl)
            repl = self._basetype(repl)
            comprepl = _compile_repl(repl, self)
            replf = lambda x: x._expand(comprepl)

        parts = []
        if count > 0:
            iterator = zip(range(count), self.finditer(string))
        else:
            iterator = zip(range(2 * len(string)), self.finditer(string))
        position = 0

        lasti = -1
        for i, match in iterator:
            parts.append(self._basetype(string[position : match.start()]))
            position = match.end()
            parts += replf(match)
            lasti = i

        parts.append(self._basetype(string[position:]))

        return (self._basetype().join(parts), lasti + 1)

    def __eq__(self, other):
        return self.pattern == other.pattern and self.flags == other.flags

    def __repr__(self):
        # These flags fo not need printing
        newflags = self.flags & (~UNICODE)
        newflags &= ~BYTEPATTERN

        if newflags:
            return f"re.compile({repr(self.pattern)[:201]}, {repr(newflags)})"
        else:
            return f"re.compile({repr(self.pattern)[:201]})"

    def __hash__(self):
        return hash((self.pattern, self.flags))


_cache = {}


def _compile(pattern, flags=0):
    if isinstance(pattern, Pattern):
        if pattern.flags == flags:
            return pattern
        else:
            pattern = pattern.pattern
    if (pattern, flags) in _cache:
        return _cache[(pattern, flags)]
    res = Pattern(pattern, flags)
    _cache[(pattern, flags)] = res
    _cache[(pattern, res.flags)] = res
    return res


_repl_cache = {}


def _compile_repl(repl, pattern):
    if not (repl, pattern) in _repl_cache:
        _repl_cache[(repl, pattern)] = sre_parse.parse_template(repl, pattern)
    return _repl_cache[(repl, pattern)]


error = constants.error

# ---------------------------------------- CODE FROM re.py -----------------------
# with only slight modifications to remove stuff defined above
import enum

try:
    import _locale
except ImportError:
    _locale = None


# public symbols
__all__ = [
    "match",
    "fullmatch",
    "search",
    "sub",
    "subn",
    "split",
    "findall",
    "finditer",
    "compile",
    "purge",
    "template",
    "escape",
    "error",
    "Pattern",
    "Match",
    "A",
    "I",
    "L",
    "M",
    "S",
    "X",
    "U",
    "ASCII",
    "IGNORECASE",
    "LOCALE",
    "MULTILINE",
    "DOTALL",
    "VERBOSE",
    "UNICODE",
]


class RegexFlag(enum.IntFlag):
    ASCII = A = constants.SRE_FLAG_ASCII  # assume ascii "locale"
    IGNORECASE = I = constants.SRE_FLAG_IGNORECASE  # ignore case
    LOCALE = L = constants.SRE_FLAG_LOCALE  # assume current 8-bit locale
    UNICODE = U = constants.SRE_FLAG_UNICODE  # assume unicode "locale"
    MULTILINE = M = constants.SRE_FLAG_MULTILINE  # make anchors look for newline
    DOTALL = S = constants.SRE_FLAG_DOTALL  # make dot match newline
    VERBOSE = X = constants.SRE_FLAG_VERBOSE  # ignore whitespace and comments
    # sre extensions (experimental, don't rely on these)
    TEMPLATE = T = constants.SRE_FLAG_TEMPLATE  # disable backtracking
    DEBUG = constants.SRE_FLAG_DEBUG  # dump pattern after compilation
    # added flag
    STRICTUNI = constants.SRE_FLAG_STRICT_UNICODE
    BYTEPATTERN = constants.SRE_FLAG_BYTE_PATTERN

    def __repr__(self):
        if self._name_ is not None:
            return f"re.{self._name_}"
        value = self._value_
        members = []
        negative = value < 0
        if negative:
            value = ~value
        for m in self.__class__:
            if value & m._value_:
                value &= ~m._value_
                members.append(f"re.{m._name_}")
        if value:
            members.append(hex(value))
        res = "|".join(members)
        if negative:
            if len(members) > 1:
                res = f"~({res})"
            else:
                res = f"~{res}"
        return res

    __str__ = object.__str__


globals().update(RegexFlag.__members__)


# --------------------------------------------------------------------
# public interface


def match(pattern, string, flags=0):
    """Try to apply the pattern at the start of the string, returning
    a Match object, or None if no match was found."""
    return _compile(pattern, flags).match(string)


def fullmatch(pattern, string, flags=0):
    """Try to apply the pattern to all of the string, returning
    a Match object, or None if no match was found."""
    return _compile(pattern, flags).fullmatch(string)


def search(pattern, string, flags=0):
    """Scan through string looking for a match to the pattern, returning
    a Match object, or None if no match was found."""
    return _compile(pattern, flags).search(string)


def sub(pattern, repl, string, count=0, flags=0):
    """Return the string obtained by replacing the leftmost
    non-overlapping occurrences of the pattern in string by the
    replacement repl.  repl can be either a string or a callable;
    if a string, backslash escapes in it are processed.  If it is
    a callable, it's passed the Match object and must return
    a replacement string to be used."""
    return _compile(pattern, flags).sub(repl, string, count)


def subn(pattern, repl, string, count=0, flags=0):
    """Return a 2-tuple containing (new_string, number).
    new_string is the string obtained by replacing the leftmost
    non-overlapping occurrences of the pattern in the source
    string by the replacement repl.  number is the number of
    substitutions that were made. repl can be either a string or a
    callable; if a string, backslash escapes in it are processed.
    If it is a callable, it's passed the Match object and must
    return a replacement string to be used."""
    return _compile(pattern, flags).subn(repl, string, count)


def split(pattern, string, maxsplit=0, flags=0):
    """Split the source string by the occurrences of the pattern,
    returning a list containing the resulting substrings.  If
    capturing parentheses are used in pattern, then the text of all
    groups in the pattern are also returned as part of the resulting
    list.  If maxsplit is nonzero, at most maxsplit splits occur,
    and the remainder of the string is returned as the final element
    of the list."""
    return _compile(pattern, flags).split(string, maxsplit)


def findall(pattern, string, flags=0):
    """Return a list of all non-overlapping matches in the string.

    If one or more capturing groups are present in the pattern, return
    a list of groups; this will be a list of tuples if the pattern
    has more than one group.

    Empty matches are included in the result."""
    return _compile(pattern, flags).findall(string)


def finditer(pattern, string, flags=0):
    """Return an iterator over all non-overlapping matches in the
    string.  For each match, the iterator returns a Match object.

    Empty matches are included in the result."""
    return _compile(pattern, flags).finditer(string)


def compile(pattern, flags=0):
    "Compile a regular expression pattern, returning a Pattern object."
    return _compile(pattern, flags)


def purge():
    "Clear the regular expression caches"
    _cache.clear()
    _repl_cache.clear()


def template(pattern, flags=0):
    "Compile a template pattern, returning a Pattern object"
    return _compile(pattern, flags | T)


# SPECIAL_CHARS
# closing ')', '}' and ']'
# '-' (a range in character set)
# '&', '~', (extended character set operations)
# '#' (comment) and WHITESPACE (ignored) in verbose mode
_special_chars_map = {i: "\\" + chr(i) for i in b"()[]{}?*+-|^$\\.&~# \t\n\r\v\f"}


def escape(pattern):
    """
    Escape special characters in a string.
    """
    if isinstance(pattern, str):
        return pattern.translate(_special_chars_map)
    else:
        pattern = str(pattern, "latin1")
        return pattern.translate(_special_chars_map).encode("latin1")


# register myself for pickling

import copyreg


def _pickle(p):
    return _compile, (p.pattern, p.flags)


copyreg.pickle(Pattern, _pickle, _compile)


class Scanner:
    pass
