from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from features.F2 import duplicate_finder
from shared import compose, search_meili, wait_for


def _compose_paths() -> tuple[Path, Path, Path]:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    return compose_file, workdir, output_dir


def _prepare_env(workdir: Path, output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')

    input_dir = workdir / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    shutil.copytree(Path(__file__).with_name("input"), input_dir)
    return input_dir


def _stat_info(path: Path) -> tuple[int, float, str]:
    stat = path.stat()
    return (
        stat.st_size,
        duplicate_finder.truncate_mtime(stat.st_mtime),
        duplicate_finder.compute_hash(path),
    )


def _run_once(compose_file: Path, workdir: Path, output_dir: Path) -> tuple[
    Path,
    Path,
    dict[str, tuple[int, float, str]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    input_dir = _prepare_env(workdir, output_dir)
    info = {name: _stat_info(input_dir / name) for name in ["a.txt", "b.txt", "c.txt"]}
    compose(compose_file, workdir, "up", "-d")
    by_id_dir = output_dir / "metadata" / "by-id"
    wait_for(
        lambda: by_id_dir.exists() and any(by_id_dir.iterdir()), message="metadata"
    )
    by_path_dir = output_dir / "metadata" / "by-path"
    dup_docs = search_meili(compose_file, workdir, "copies = 2")
    uniq_docs = search_meili(compose_file, workdir, "copies = 1")
    assert len(dup_docs) == 1
    assert len(uniq_docs) == 1
    return by_id_dir, by_path_dir, info, dup_docs, uniq_docs


def _sync(compose_file: Path, workdir: Path, output_dir: Path) -> None:
    compose(compose_file, workdir, "up", "-d")
    by_id_dir = output_dir / "metadata" / "by-id"
    wait_for(
        lambda: by_id_dir.exists() and any(by_id_dir.iterdir()), message="metadata"
    )


def test_s1_initial_sync_with_duplicates(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        by_id_dir, by_path_dir, _, _, uniq_docs = _run_once(
            compose_file, workdir, output_dir
        )

        dirs = [d for d in by_id_dir.iterdir() if d.is_dir()]
        assert len(dirs) == 2

        link_a = by_path_dir / "a.txt"
        link_b = by_path_dir / "b.txt"
        link_c = by_path_dir / "c.txt"
        assert link_a.is_symlink() and link_b.is_symlink() and link_c.is_symlink()
        assert link_a.resolve() == link_b.resolve()
        assert link_c.resolve().name == uniq_docs[0]["id"]
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s2_document_fields_populated(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        _, _, info, dup_docs, uniq_docs = _run_once(compose_file, workdir, output_dir)

        uniq = uniq_docs[0]
        size, mtime, file_hash = info["c.txt"]
        assert uniq["id"] == file_hash
        assert uniq["paths"] == {"c.txt": mtime}
        assert uniq["paths_list"] == ["c.txt"]
        assert uniq["size"] == size
        assert uniq["copies"] == 1
        assert uniq["type"] == "text/plain"
        assert isinstance(uniq["mtime"], float)

        dup = dup_docs[0]
        size_a, mtime_a, hash_a = info["a.txt"]
        size_b, mtime_b, _ = info["b.txt"]
        assert dup["id"] == hash_a
        assert dup["size"] == size_a
        assert dup["paths"] == {"a.txt": mtime_a, "b.txt": mtime_b}
        assert sorted(dup["paths_list"]) == ["a.txt", "b.txt"]
        assert dup["copies"] == 2
        assert dup["type"] == "text/plain"
        assert isinstance(dup["mtime"], float)
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s3_search_by_single_criterion(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        _run_once(compose_file, workdir, output_dir)
        docs = search_meili(compose_file, workdir, "copies = 1")
        assert all(doc["copies"] == 1 for doc in docs)
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s4_search_by_multiple_criteria(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        _, _, info, _, uniq_docs = _run_once(compose_file, workdir, output_dir)
        size = info["c.txt"][0]
        docs = search_meili(
            compose_file,
            workdir,
            f'size = {size} AND type = "text/plain"',
        )
        assert any(doc["id"] == uniq_docs[0]["id"] for doc in docs)
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s5_add_new_duplicate(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        by_id_dir, by_path_dir, _, _, uniq_docs = _run_once(
            compose_file, workdir, output_dir
        )

        shutil.copy(workdir / "input" / "c.txt", workdir / "input" / "c2.txt")
        _sync(compose_file, workdir, output_dir)

        docs = search_meili(compose_file, workdir, 'paths_list = "c2.txt"')
        assert docs
        doc = docs[0]
        assert doc["id"] == uniq_docs[0]["id"]
        assert doc["copies"] == 2
        assert {"c.txt", "c2.txt"} <= set(doc["paths"].keys())
        assert len([d for d in by_id_dir.iterdir() if d.is_dir()]) == 2
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s6_delete_one_duplicate(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        _, by_path_dir, _, dup_docs, _ = _run_once(compose_file, workdir, output_dir)
        dup_id = dup_docs[0]["id"]

        (workdir / "input" / "b.txt").unlink()
        _sync(compose_file, workdir, output_dir)

        docs = search_meili(compose_file, workdir, f'id = "{dup_id}"')
        assert docs[0]["copies"] == 1
        assert not (by_path_dir / "b.txt").exists()
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s7_delete_last_remaining_copy(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        by_id_dir, by_path_dir, _, _, uniq_docs = _run_once(
            compose_file, workdir, output_dir
        )
        uniq_id = uniq_docs[0]["id"]

        (workdir / "input" / "c.txt").unlink()
        _sync(compose_file, workdir, output_dir)

        with pytest.raises(AssertionError):
            search_meili(compose_file, workdir, f'id = "{uniq_id}"', timeout=5)
        assert not (by_path_dir / "c.txt").exists()
        assert uniq_id not in {p.name for p in by_id_dir.iterdir()}
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s8_file_content_changes(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        by_id_dir, by_path_dir, _, dup_docs, _ = _run_once(
            compose_file, workdir, output_dir
        )
        old_id = dup_docs[0]["id"]

        (workdir / "input" / "b.txt").write_text("changed")
        _sync(compose_file, workdir, output_dir)

        docs = search_meili(compose_file, workdir, 'paths_list = "b.txt"')
        new_id = docs[0]["id"]
        assert new_id != old_id
        assert (by_id_dir / new_id).exists()
        assert (by_id_dir / old_id).exists()
        assert (by_path_dir / "b.txt").resolve().name == new_id
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s9_symlink_integrity(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        by_id_dir, by_path_dir, _, _, _ = _run_once(compose_file, workdir, output_dir)

        links = [by_path_dir / name for name in ["a.txt", "b.txt", "c.txt"]]
        targets = [link.resolve() for link in links]
        assert all(by_id_dir in t.parents for t in targets)
        assert all(not Path(os.readlink(link)).is_absolute() for link in links)

        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
        _sync(compose_file, workdir, output_dir)

        for link, target in zip(links, targets, strict=True):
            assert link.resolve() == target
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s10_search_returns_latest_metadata(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    try:
        _, _, _, _, uniq_docs = _run_once(compose_file, workdir, output_dir)

        shutil.copy(workdir / "input" / "c.txt", workdir / "input" / "extra.txt")
        _sync(compose_file, workdir, output_dir)

        docs = search_meili(compose_file, workdir, "copies > 1")
        assert any("extra.txt" in doc.get("paths_list", []) for doc in docs)
        assert any(doc["id"] == uniq_docs[0]["id"] for doc in docs)
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
