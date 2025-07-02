import json
import importlib
import threading
import time


def test_run_server_processes_tasks(monkeypatch):
    rs = importlib.reload(
        importlib.import_module("features.F4.home_index_module.run_server")
    )

    class DummyRedis:
        def __init__(self, *args, **kwargs):
            self.lists = {
                "mod:check": [],
                "mod:run": [],
                "modules:done": [],
                "mod:run:processing": [],
            }
            self.sorted = {
                "mod:check:processing": {},
                "mod:run:processing": {},
                "timeouts": {},
            }

        def rpush(self, key, val):
            self.lists.setdefault(key, []).append(val)

        def lpop(self, key):
            if self.lists[key]:
                return self.lists[key].pop(0)
            return None

        def blmove(self, source, dest, _src_side, _dest_side, timeout=0):
            if self.lists[source]:
                val = self.lists[source].pop(0)
                self.lists.setdefault(dest, []).append(val)
                return val
            raise KeyboardInterrupt

        def blpop(self, key, timeout=0):
            if self.lists[key]:
                return key, self.lists[key].pop(0)
            raise KeyboardInterrupt

        def zadd(self, key, mapping):
            self.sorted.setdefault(key, {}).update(mapping)

        def zrem(self, key, member):
            self.sorted.get(key, {}).pop(member, None)

        def zscore(self, key, member):
            return self.sorted.get(key, {}).get(member)

        def lrem(self, key, _count, value):
            self.lists[key] = [v for v in self.lists.get(key, []) if v != value]

        def pipeline(self) -> "DummyRedis":
            return self

        def execute(self) -> None:
            pass

        def __enter__(self) -> "DummyRedis":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            pass

    dummy = DummyRedis()
    monkeypatch.setattr(rs, "make_redis_client", lambda: dummy)

    def run():
        try:
            rs.QUEUE_NAME = "mod"
            rs.REDIS_HOST = "redis"
            rs.TIMEOUT = 1
            rs.run_server(lambda a, b, c: True, lambda a, b, c: b)
        except KeyboardInterrupt:
            pass

    dummy.rpush("mod:check", json.dumps({"id": "1", "paths": {"a": 1}}))
    t = threading.Thread(target=run)
    t.start()
    t.join()

    assert json.loads(dummy.lists["modules:done"][0])["document"]["id"] == "1"
    assert not dummy.sorted["timeouts"]
    assert not dummy.lists["mod:run:processing"]


def test_run_server_respects_resource_share(monkeypatch):
    rs = importlib.import_module("features.F4.home_index_module.run_server")

    class DummyRedis:
        def __init__(self, *args, **kwargs):
            self.lists = {
                "mod:check": [],
                "mod:run": [],
                "modules:done": [],
                "mod:run:processing": [],
                "gpu:share": [],
            }
            self.sorted = {
                "mod:check:processing": {},
                "mod:run:processing": {},
                "timeouts": {},
            }

        def rpush(self, key, val):
            self.lists.setdefault(key, []).append(val)

        def lrange(self, key, _start, _end):
            return list(self.lists.get(key, []))

        def lindex(self, key, idx):
            try:
                return self.lists[key][idx]
            except (IndexError, KeyError):
                return None

        def lpop(self, key):
            if self.lists.get(key):
                return self.lists[key].pop(0)
            return None

        def blmove(self, source, dest, _src_side, _dest_side, timeout=0):
            if self.lists[source]:
                val = self.lists[source].pop(0)
                self.lists.setdefault(dest, []).append(val)
                return val
            raise KeyboardInterrupt

        def blpop(self, key, timeout=0):
            if self.lists[key]:
                return key, self.lists[key].pop(0)
            raise KeyboardInterrupt

        def zadd(self, key, mapping):
            self.sorted.setdefault(key, {}).update(mapping)

        def zrem(self, key, member):
            self.sorted.get(key, {}).pop(member, None)

        def zscore(self, key, member):
            return self.sorted.get(key, {}).get(member)

        def lrem(self, key, _count, value):
            self.lists[key] = [v for v in self.lists.get(key, []) if v != value]

        def pipeline(self) -> "DummyRedis":
            return self

        def execute(self) -> None:
            pass

        def __enter__(self) -> "DummyRedis":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            pass

    dummy = DummyRedis()
    monkeypatch.setenv("RESOURCE_SHARES", "- name: gpu\n  seconds: 1")
    monkeypatch.setenv("WORKER_ID", "worker1")
    rs = importlib.reload(
        importlib.import_module("features.F4.home_index_module.run_server")
    )
    monkeypatch.setattr(rs, "make_redis_client", lambda: dummy)

    def run():
        try:
            rs.QUEUE_NAME = "mod"
            rs.REDIS_HOST = "redis"
            rs.run_server(lambda a, b, c: True, lambda a, b, c: b)
        except KeyboardInterrupt:
            pass

    dummy.rpush("mod:run", json.dumps({"id": "1", "paths": {"a": 1}}))
    t = threading.Thread(target=run)
    t.start()
    t.join()

    assert dummy.lists["gpu:share"][0] == "worker1"


def test_process_timeouts_requeues_expired(monkeypatch):
    import importlib
    import main as hi

    importlib.reload(hi)

    doc = {"id": "1", "paths": {"a": 1}}
    doc_json = json.dumps(doc)
    key = json.dumps({"q": "mod:run", "d": doc_json})

    class DummyRedis:
        def __init__(self) -> None:
            self.lists = {"mod:run": [], "mod:run:processing": [doc_json]}
            self.sorted = {"timeouts": {key: time.time() - 1}}

        def zpopmin(self, key: str, count: int = 1) -> list[tuple[str, float]]:
            if self.sorted.get(key):
                member, score = self.sorted[key].popitem()
                return [(member, score)]
            return []

        def zadd(self, key: str, mapping: dict[str, float]) -> None:
            self.sorted.setdefault(key, {}).update(mapping)

        def lrem(self, key: str, _count: int, value: str) -> None:
            self.lists[key] = [v for v in self.lists.get(key, []) if v != value]

        def lpush(self, key: str, value: str) -> None:
            self.lists.setdefault(key, []).insert(0, value)

        def pipeline(self) -> "DummyRedis":
            return self

        def execute(self) -> None:
            pass

        def __enter__(self) -> "DummyRedis":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            pass

    dummy = DummyRedis()
    monkeypatch.setattr(
        hi.modules_f4, "redis", type("R", (), {"Redis": lambda **kw: dummy})
    )

    assert hi.modules_f4.process_timeouts(dummy) is True
    assert dummy.lists["mod:run"][0] == doc_json
    assert not dummy.lists["mod:run:processing"]
