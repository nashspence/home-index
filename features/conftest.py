# ruff: noqa: E402
from tests.conftest import stub_dependencies as _base_stub_dependencies
import pytest


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    gen = _base_stub_dependencies._fixture_function(monkeypatch)
    next(gen)
    import importlib
    import sys

    sys.modules.pop("features.F1", None)
    import features.F1 as f1

    importlib.reload(f1)
    try:
        yield
    finally:
        next(gen, None)


__all__ = ["stub_dependencies"]
