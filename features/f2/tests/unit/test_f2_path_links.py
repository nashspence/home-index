import os
from pathlib import Path


def test_link_and_unlink(monkeypatch, tmp_path: Path):
    import features.f2.path_links as pl
    import features.f2.metadata_store as ms

    by_id = tmp_path / "by-id"
    by_path = tmp_path / "by-path"
    monkeypatch.setenv("BY_ID_DIRECTORY", str(by_id))
    monkeypatch.setenv("BY_PATH_DIRECTORY", str(by_path))
    ms.ensure_directories()
    target = by_id / "123"
    target.mkdir(parents=True)

    pl.link_path("sub/file.txt", "123")
    link = by_path / "sub" / "file.txt"
    assert link.is_symlink()
    assert os.readlink(link) == os.path.relpath(target, link.parent)

    pl.unlink_path("sub/file.txt")
    assert not link.exists()
    assert not (by_path / "sub").exists()
