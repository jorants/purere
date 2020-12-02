"""
This file contains tests for full string matching.
The output is compared to the native implementation.
"""

import re
from purere import matcher
import pytest

raw_testdata = {
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
        "x"*20+"y",
        "x"*21,
    ],
}

testdata = [(pat,s) for pat,strings in raw_testdata.items() for s in strings]

@pytest.mark.parametrize("pattern,s",testdata)
def test_full_match(pattern,s):
    native = re.compile("^"+pattern+"$")
    pyreimp = matcher.Pattern(pattern)
    assert bool(pyreimp.matches(s)) == bool(native.match(s))


