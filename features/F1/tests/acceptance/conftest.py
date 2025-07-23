import logging

import pytest


@pytest.fixture(autouse=True)
def _debug_logging():
    logging.basicConfig(level=logging.DEBUG, force=True)
    yield
