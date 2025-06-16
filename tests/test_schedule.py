import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))


def test_parse_cron_env_parses_expression(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))
    monkeypatch.setenv("CRON_EXPRESSION", "15 2 * * 3")
    import home_index.main as hi
    import importlib
    importlib.reload(hi)
    result = hi.parse_cron_env()
    assert result == {
        "minute": "15",
        "hour": "2",
        "day": "*",
        "month": "*",
        "day_of_week": "3",
    }


def test_parse_cron_env_invalid(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs2"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))
    monkeypatch.setenv("CRON_EXPRESSION", "15 2 * *")
    import home_index.main as hi
    import importlib
    importlib.reload(hi)
    with pytest.raises(ValueError):
        hi.parse_cron_env()
