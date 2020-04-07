# -*- coding: utf-8 -*-
# definitions for pytest

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--runnexus", action="store_true", default=False, help="run Nexus tests"
    )

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")
    config.addinivalue_line("nexus", "nexus: mark test as requiring nexus")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--runslow"):
        skip_slow = pytest.mark.skip(reason="need --runslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    if not config.getoption("--runnexus"):
        skip_nexus = pytest.mark.skip(reason="need --runnexus option to run")
        for item in items:
            if "nexus" in item.keywords:
                item.add_marker(skip_nexus)
    