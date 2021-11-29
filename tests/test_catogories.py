import pytest
import purere.constants
from purere.topy import get_category_condition
import sre_constants
import _sre


cats = [v for v in dir(sre_constants) if v.startswith("CATEGORY_")]


@pytest.mark.parametrize("catname", cats)
def test_def_equal(catname):

    purere_constant = getattr(purere.constants, catname)
    # get a function that tests a character using out implementation
    try:
        code = get_category_condition(
            purere_constant, "c", flags=purere.constants.SRE_FLAG_STRICT_UNICODE
        )
    except ValueError:
        pytest.skip(f"{catname} not implemented yet")

    if "unicodedata" in code:
        pycode = f"def f(c):\n import unicodedata\n num=ord\n return {code}"
    else:
        pycode = f"def f(c):\n num=ord\n return {code}"
    res = {}
    exec(pycode, res)
    f = res["f"]

    # get a function from buildin sre regex
    real_sre_constant = getattr(sre_constants, catname)
    code = [
        sre_constants.IN,
        4,
        sre_constants.CATEGORY,
        real_sre_constant,
        sre_constants.FAILURE,
        sre_constants.SUCCESS,
    ]

    srereg = _sre.compile(None, 0, code, 0, {}, (None,))

    for c in range(0x110000):
        char = chr(c)
        assert f(char) == (
            srereg.match(char) is not None
        ), f"On value {repr(char)} for {catname}"
