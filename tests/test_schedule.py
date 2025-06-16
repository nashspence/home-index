import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
import home_index.main as hi


def test_parse_cron_env_parses_expression(monkeypatch):
    monkeypatch.setenv("CRON_EXPRESSION", "15 2 * * 3")
    result = hi.parse_cron_env()
    assert result == {
        "minute": "15",
        "hour": "2",
        "day": "*",
        "month": "*",
        "day_of_week": "3",
    }


def test_parse_cron_env_invalid(monkeypatch):
    monkeypatch.setenv("CRON_EXPRESSION", "15 2 * *")
    with pytest.raises(ValueError):
        hi.parse_cron_env()
