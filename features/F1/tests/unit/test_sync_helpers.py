import os
import importlib
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def reload_sync():
    import features.F1.sync as sync

    importlib.reload(sync)


# --- _safe_mkdir -------------------------------------------------------------


def test_safe_mkdir_creates_directory(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b"
    from features.F1 import sync

    sync._safe_mkdir(target)
    assert target.exists()


def test_safe_mkdir_ignores_permission_error(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "dir"

    def fake_mkdir(self, *args, **kwargs):
        if self == target:
            raise PermissionError()
        return orig_mkdir(self, *args, **kwargs)

    from features.F1 import sync

    orig_mkdir = Path.mkdir
    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    sync._safe_mkdir(target)  # should not raise


def test_safe_mkdir_ignores_read_only(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "dir2"

    def fake_mkdir(self, *args, **kwargs):
        if self == target:
            raise OSError(30, "ro")
        return orig_mkdir(self, *args, **kwargs)

    from features.F1 import sync

    orig_mkdir = Path.mkdir
    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    sync._safe_mkdir(target)  # should not raise


# --- compute_hash ------------------------------------------------------------


def test_compute_hash_returns_stat_and_hash(monkeypatch, tmp_path: Path) -> None:
    file_path = tmp_path / "f.txt"
    file_path.write_text("hi")

    from features.F1 import sync

    monkeypatch.setattr(sync.duplicate_finder, "compute_hash", lambda p: "h")
    path, h, stat = sync.compute_hash(file_path)
    assert path == file_path
    assert h == "h"
    assert isinstance(stat, os.stat_result)


# --- module_metadata_path ----------------------------------------------------


def test_module_metadata_path_creates(monkeypatch, tmp_path: Path) -> None:
    from features.F1 import sync

    monkeypatch.setattr(sync.metadata_store, "by_id_directory", lambda: tmp_path)
    result = sync.module_metadata_path("id1", "mod")
    assert result == tmp_path / "id1" / "mod"
    assert result.is_dir()


# --- is_apple_double ---------------------------------------------------------


def test_is_apple_double_detects_header(tmp_path: Path) -> None:
    from features.F1 import sync

    f = tmp_path / "file"
    f.write_bytes(b"\x00\x05\x16\x07rest")
    assert sync.is_apple_double(f)


def test_is_apple_double_false(tmp_path: Path) -> None:
    from features.F1 import sync

    f = tmp_path / "file2"
    f.write_bytes(b"\x00\x00\x00\x00")
    assert not sync.is_apple_double(f)


# --- get_mime_type ----------------------------------------------------------


def test_get_mime_type_uses_magic(monkeypatch, tmp_path: Path) -> None:
    from features.F1 import sync

    f = tmp_path / "file.txt"
    f.write_text("hello")

    class DummyMagic:
        def __init__(self, mime=True):
            pass

        def from_file(self, path: str) -> str:
            return "text/plain"

    import sys

    monkeypatch.setattr(sync, "magic_mime", None)
    monkeypatch.setattr(sys.modules["magic"], "Magic", DummyMagic)
    assert sync.get_mime_type(f) == "text/plain"


def test_get_mime_type_apple_double(monkeypatch, tmp_path: Path) -> None:
    from features.F1 import sync

    f = tmp_path / "file.adf"
    f.write_bytes(b"\x00\x05\x16\x07rest")

    class DummyMagic:
        def __init__(self, mime=True):
            pass

        def from_file(self, path: str) -> str:
            return "application/octet-stream"

    import sys

    monkeypatch.setattr(sync, "magic_mime", None)
    monkeypatch.setattr(sys.modules["magic"], "Magic", DummyMagic)
    monkeypatch.setattr(sync, "is_apple_double", lambda p: True)
    assert sync.get_mime_type(f) == "multipart/appledouble"


def test_get_mime_type_fallback_guess(monkeypatch, tmp_path: Path) -> None:
    from features.F1 import sync

    f = tmp_path / "file.bin"
    f.write_bytes(b"data")

    class DummyMagic:
        def __init__(self, mime=True):
            pass

        def from_file(self, path: str) -> str:
            return "application/octet-stream"

    import sys

    monkeypatch.setattr(sync, "magic_mime", None)
    monkeypatch.setattr(sys.modules["magic"], "Magic", DummyMagic)
    monkeypatch.setattr(sync, "is_apple_double", lambda p: False)
    monkeypatch.setattr(
        sync.mimetypes, "guess_type", lambda *a, **k: ("application/foo", None)
    )
    assert sync.get_mime_type(f) == "application/foo"


# --- run_async_in_loop & run_in_process -------------------------------------


def test_run_async_in_loop_executes() -> None:
    from features.F1 import sync

    recorded: dict[str, int] = {}

    async def coro(x: int) -> None:
        recorded["val"] = x

    sync.run_async_in_loop(coro, 3)
    assert recorded["val"] == 3


def test_run_in_process_invokes(monkeypatch) -> None:
    from features.F1 import sync

    called: dict[str, object] = {}

    def fake_run_async(func, *args):
        called["func"] = func
        called["args"] = args

    class DummyProcess:
        def __init__(self, target, args):
            self.target = target
            self.args = args
            called["created"] = True

        def start(self):
            self.target(*self.args)
            called["started"] = True

        def join(self):
            called["joined"] = True

    monkeypatch.setattr(sync, "run_async_in_loop", fake_run_async)
    monkeypatch.setattr(sync, "Process", DummyProcess)

    async def coro(a: int) -> None:
        called["coro"] = a

    sync.run_in_process(coro, 7)

    assert called["func"] is coro
    assert called["args"] == (7,)
    assert called["started"] and called["joined"]
