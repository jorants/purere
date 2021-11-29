import pytest
import purere
import re
from .re_tests import tests


@pytest.mark.parametrize("test", tests)
def test_equal(test):
    reg = test[0]
    s = test[1]

    try:
        repat = re.compile(reg)
        reresult = repat.search(s)
    except re.error as e:
        reresult = -1

    if reresult == -1:
        try:
            purerepat = purere.compile(reg)
            purereresult = purerepat.search(s)
        except Exception as e:
            return
        raise Exception(f"Expected error on {reg}")

    try:
        purerepat = purere.compile(reg)
    except ValueError as e:
        # if "Unknown" in  str(e):
        #     pytest.skip("Ignoring unknown opcodes")
        raise e

    purereresult = purerepat.search(s)

    if reresult in {-1, None} or purereresult in {-1, None}:
        assert reresult == purereresult
    else:
        assert reresult.regs == purereresult.regs
