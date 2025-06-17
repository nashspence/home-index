import sys
from pathlib import Path
import importlib
import time
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))


def test_retry_helper_stops_when_a_call_succeeds(monkeypatch, tmp_path):
    monkeypatch.setenv("MODULES", "")
    monkeypatch.setenv("LOGGING_DIRECTORY", str(tmp_path))
    import home_index.main as hi
    importlib.reload(hi)
    sleeps = []
    monkeypatch.setattr(time, 'sleep', lambda s: sleeps.append(s))
    attempts = {'c': 0}

    def fn():
        attempts['c'] += 1
        if attempts['c'] < 3:
            raise ValueError('no')
        return 'ok'

    result = hi.retry_until_ready(fn, 'fail', seconds=3)
    assert result == 'ok'
    assert attempts['c'] == 3
    assert sleeps == [1, 1]


def test_retry_helper_fails_after_repeated_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("MODULES", "")
    monkeypatch.setenv("LOGGING_DIRECTORY", str(tmp_path))
    import home_index.main as hi
    importlib.reload(hi)
    sleeps = []
    monkeypatch.setattr(time, 'sleep', lambda s: sleeps.append(s))

    def fn():
        raise ValueError('no')

    with pytest.raises(RuntimeError):
        hi.retry_until_ready(fn, 'fail', seconds=2)
    assert sleeps == [1]
