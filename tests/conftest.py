def pytest_runtest_makereport(item, call):
    from _pytest.runner import (
        pytest_runtest_makereport as orig_pytest_runtest_makereport,
    )

    tr = orig_pytest_runtest_makereport(item, call)

    if call.excinfo is not None:
        if call.excinfo.type == NotImplementedError:
            tr.outcome = "skipped"
            tr.wasxfail = "reason: Not implemented:" + call.excinfo.value.args[0]

    return tr
