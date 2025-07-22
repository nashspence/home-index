import asyncio
import importlib
import json


def _reload_modules(monkeypatch):
    from features.F4 import modules as modules_f4

    importlib.reload(modules_f4)
    from features.F2 import search_index

    importlib.reload(search_index)
    monkeypatch.setattr(modules_f4, "module_values", [])


def test_archive_files_first(monkeypatch):
    _reload_modules(monkeypatch)
    from features.F2 import search_index
    from features.F4 import modules as modules_f4

    doc_arch = {
        "id": "1",
        "paths": {"archive/drive1/b.txt": 1.0},
        "paths_list": ["archive/drive1/b.txt"],
        "mtime": 1.0,
        "next": "mod",
        "has_archive_paths": True,
        "offline": False,
    }

    doc_normal = {
        "id": "2",
        "paths": {"a.txt": 1.0},
        "paths_list": ["a.txt"],
        "mtime": 1.0,
        "next": "mod",
        "has_archive_paths": False,
        "offline": False,
    }

    async def fake_get_jobs(name):
        raise AssertionError("should not call get_all_pending_jobs")

    monkeypatch.setattr(search_index, "get_all_pending_jobs", fake_get_jobs)

    class DummyRedis:
        def __init__(self):
            self.storage = {}

        def rpush(self, key, val):
            self.storage.setdefault(key, []).append(val)

        def lrange(self, key, _start, _end):
            return self.storage.get(key, [])

    dummy = DummyRedis()
    result = asyncio.run(
        modules_f4.service_module_queue("mod", dummy, [doc_normal, doc_arch])
    )
    assert result
    pushed = dummy.storage["mod:check"]
    assert json.loads(pushed[0])["id"] == "1"
    assert json.loads(pushed[1])["id"] == "2"
