from pathlib import Path

import pytest


def test_truncate_mtime_rounds_down():
    import features.f2.duplicate_finder as df

    assert df.truncate_mtime(1.23456) == pytest.approx(1.2345)


def test_compute_hash_returns_string(tmp_path: Path):
    import features.f2.duplicate_finder as df

    file_path = tmp_path / "file.txt"
    file_path.write_text("hi")
    assert df.compute_hash(file_path) == "0"


def test_determine_hash_uses_cached(monkeypatch, tmp_path: Path):
    import features.f2.duplicate_finder as df

    index_dir = tmp_path
    file_path = index_dir / "a.txt"
    file_path.write_text("data")

    stat = file_path.stat()
    prev_hash = "cached"
    docs = {prev_hash: {"paths": {"a.txt": df.truncate_mtime(stat.st_mtime)}}}
    hashes = {"a.txt": prev_hash}

    def fake_compute(_):
        raise AssertionError("compute_hash called")

    monkeypatch.setattr(df, "compute_hash", fake_compute)
    path, h, st = df.determine_hash(file_path, index_dir, docs, hashes)
    assert path == file_path
    assert h == prev_hash
    assert st.st_size == stat.st_size


def test_determine_hash_recomputes_when_mtime_changes(monkeypatch, tmp_path: Path):
    import features.f2.duplicate_finder as df

    index_dir = tmp_path
    file_path = index_dir / "b.txt"
    file_path.write_text("x")

    prev_hash = "cached"
    docs = {prev_hash: {"paths": {"b.txt": 0.0}}}
    hashes = {"b.txt": prev_hash}
    called = {}

    def fake_compute(_):
        called["yes"] = True
        return "new"

    monkeypatch.setattr(df, "compute_hash", fake_compute)
    path, h, st = df.determine_hash(file_path, index_dir, docs, hashes)
    assert path == file_path
    assert h == "new"
    assert called.get("yes")
