import pytest


def test_cron_schedules_are_parsed_from_the_environment(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))
    monkeypatch.setenv("MODULES", "")
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
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


def test_malformed_cron_expressions_raise_valueerror(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs2"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))
    monkeypatch.setenv("MODULES", "")
    monkeypatch.setenv("CRON_EXPRESSION", "15 2 * *")
    import home_index.main as hi
    import importlib

    importlib.reload(hi)
    with pytest.raises(ValueError):
        hi.parse_cron_env()


def test_scheduler_attaches_a_crontrigger_job_for_periodic_indexing(
    monkeypatch, tmp_path
):
    log_dir = tmp_path / "logs3"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))
    monkeypatch.setenv("MODULES", "")
    monkeypatch.setenv("CRON_EXPRESSION", "5 4 * * *")
    monkeypatch.setenv(
        "HELLO_VERSIONS_FILE_PATH", str(tmp_path / "hello_versions.json")
    )
    monkeypatch.delenv("DEBUG", raising=False)
    added = {}

    class DummyScheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, func, trigger, args=None, max_instances=None):
            added["trigger"] = trigger

        def start(self):
            added["started"] = True

    import home_index.main as hi
    import importlib

    importlib.reload(hi)

    monkeypatch.setattr(hi, "BackgroundScheduler", lambda: DummyScheduler())

    async def dummy_run_modules():
        added["ran"] = True

    monkeypatch.setattr(hi, "run_modules", dummy_run_modules)

    async def dummy_async():
        return None

    monkeypatch.setattr(hi, "init_meili", dummy_async)
    monkeypatch.setattr(hi, "sync_documents", dummy_async)

    import asyncio

    asyncio.run(hi.main())

    assert added.get("trigger") is not None
    assert added.get("started") is True
