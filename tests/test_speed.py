import pytest
import purere
import timeit
import re

regexes = r"""
[\w\.+-]+@[\w\.-]+\.[\w\.-]+
[\w]+://[^/\s?#]+[^\s?#]+(?:\?[^\s#]*)?(?:#[^\s]*)?
(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9])
""".strip().split(
    "\n"
)


@pytest.mark.parametrize("regex", regexes)
def test_time_compile(regex):
    # not really fair as we ignore subsets and just match the first occurence, after which everything is taken

    start = timeit.default_timer()
    purere.compile(regex)
    stop = timeit.default_timer()
    localtime = stop - start

    start = timeit.default_timer()
    re.compile(regex)
    stop = timeit.default_timer()
    othertime = stop - start
    print("localtime:", localtime)
    print("othertime:", othertime)
    print("slowdown:", localtime / othertime)


#@pytest.mark.skip("Not now, to slow")
@pytest.mark.parametrize("regex", regexes)
def test_time_run(regex):
    data = open("tests/bench.txt").read()

    pat = purere.compile(regex)
    start = timeit.default_timer()
    pat.findall(data)
    stop = timeit.default_timer()
    localtime = stop - start

    pat = re.compile(regex)
    start = timeit.default_timer()
    pat.findall(data)
    stop = timeit.default_timer()
    othertime = stop - start

    print("localtime:", localtime)
    print("othertime:", othertime)
    print("slowdown:", localtime / othertime)


@pytest.mark.parametrize("num", [5, 10, 15, 20, 25])
def test_time_run_evil(num):
    data = "a" * num
    regex = "a?" * num + "a" * num

    pat = purere.compile(regex)
    start = timeit.default_timer()
    pat.fullmatch(data)
    stop = timeit.default_timer()
    localtime = stop - start

    pat = re.compile(regex)
    start = timeit.default_timer()
    pat.fullmatch(data)
    stop = timeit.default_timer()
    othertime = stop - start

    print("localtime:", localtime)
    print("othertime:", othertime)
    print("slowdown:", localtime / othertime)


from .re_tests import benchmarks


@pytest.mark.parametrize("bench", benchmarks)
def test_re_benchmarks(bench):
    "re_tests benchmarks"
    pattern, s = bench
    print(pattern)
    start = timeit.default_timer()
    p = re.compile(pattern)
    assert p.search(s)
    assert p.match(s)
    assert p.fullmatch(s)
    s2 = " " * 10000 + s + " " * 10000
    assert p.search(s2)
    assert p.match(s2, 10000)
    assert p.match(s2, 10000, 10000 + len(s))
    assert p.fullmatch(s2, 10000, 10000 + len(s))
    stop = timeit.default_timer()
    othertime = stop - start
    
    start = timeit.default_timer()
    p = purere.compile(pattern)
    assert p.search(s)
    assert p.match(s)
    assert p.fullmatch(s)
    s2 = " " * 10000 + s + " " * 10000
    assert p.search(s2)
    assert p.match(s2, 10000)
    assert p.match(s2, 10000, 10000 + len(s))
    assert p.fullmatch(s2, 10000, 10000 + len(s))
    stop = timeit.default_timer()
    localtime = stop - start

    print("localtime:", localtime)
    print("othertime:", othertime)
    print("slowdown:", localtime / othertime)
