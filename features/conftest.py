# ruff: noqa: E402
from tests.conftest import stub_dependencies as _base_stub_dependencies
import pytest


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    gen = _base_stub_dependencies._fixture_function(monkeypatch)
    next(gen)
    import importlib
    import sys

    modules_to_restore = [
        "apscheduler",
        "apscheduler.schedulers",
        "apscheduler.schedulers.background",
        "apscheduler.triggers",
        "apscheduler.triggers.interval",
        "apscheduler.triggers.cron",
    ]
    originals = {mod: sys.modules.get(mod) for mod in modules_to_restore}
    try:
        for mod in modules_to_restore:
            sys.modules.pop(mod, None)
        import apscheduler  # noqa: F401
    except ModuleNotFoundError:
        for mod, value in originals.items():
            if value is not None:
                sys.modules[mod] = value
    else:
        for mod in modules_to_restore:
            sys.modules[mod] = importlib.import_module(mod)

    sys.modules.pop("features.F1", None)
    import features.F1 as f1

    importlib.reload(f1)
    try:
        yield
    finally:
        next(gen, None)


__all__ = ["stub_dependencies"]
