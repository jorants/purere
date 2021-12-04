import pytest
import purere
import re
from .re_tests import tests


def compile_from_py(pat):
    code = "\n\n".join([purere.get_headers(),purere.compile_to_py(pat)])
    res = {}
    exec(code,res)
    return res['regex']

# same as test_equal but compile_to_py
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
            
            purerepat = compile_from_py(reg)
            purereresult = purerepat.search(s)
        except Exception as e:
            return
        raise Exception(f"Expected error on {reg}")

    try:
        purerepat = compile_from_py(reg)
    except ValueError as e:
        raise e

    purereresult = purerepat.search(s)

    if reresult in {-1, None} or purereresult in {-1, None}:
        assert reresult == purereresult
    else:
        assert reresult.regs == purereresult.regs
