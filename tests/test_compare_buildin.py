"""
This file contains tests for full string matching.
The output is compared to the native implementation.
"""

import re
import purere
import pytest

raw_testdata_fullstring = {
    "ab{2,3}":[
        "abb",
        "abc",
        ],
    "(ab)+":[
        "abac",
        "abab",
        "",
    ],
    # Exponential input for buildin re:
    "([xy]+[xz]+)+w":[
        "x"*24+"w",
        "x"*24,
    ],
}

testdata_fullstring = [(pat,s) for pat,strings in raw_testdata_fullstring.items() for s in strings]

@pytest.mark.parametrize("pattern,s",testdata_fullstring)
def test_fullmatch(pattern,s):
    nativepat = re.compile(pattern)
    purerepat = purere.compile(pattern)
    match1 = purerepat.fullmatch(s)
    match2 = nativepat.fullmatch(s)

    assert bool(match1) == bool(match2)
    if match1:
        assert match1.groups() == match2.groups()

