from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable
import pytest

from features.F2 import duplicate_finder
from shared import compose, dump_logs, search_meili, wait_for


def _run_once(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    doc_relpaths: list[str],
    setup_input: Callable[[Path], None] | None = None,
    *,
    override_ids: dict[str, str] | None = None,
    next_map: dict[str, str] | None = None,
    env_file: Path | None = None,
) -> list[str]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')

    input_dir = workdir / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    if setup_input:
        setup_input(input_dir)

    metadata_dir = output_dir / "metadata"
    by_id = metadata_dir / "by-id"
    by_path = metadata_dir / "by-path"
    by_id.mkdir(parents=True)
    by_path.mkdir(parents=True)

    doc_ids: list[str] = []
    docs_by_id: dict[str, dict[str, Any]] = {}
    for i, doc_relpath in enumerate(doc_relpaths, start=1):
        doc_path = input_dir / doc_relpath
        if override_ids and doc_relpath in override_ids:
            doc_id = override_ids[doc_relpath]
        elif doc_path.exists():
            doc_id = duplicate_finder.compute_hash(doc_path)
        else:
            doc_id = f"hash{i}"
        doc_ids.append(doc_id)
        doc = docs_by_id.get(doc_id)
        if not doc:
            doc = {
                "id": doc_id,
                "paths": {},
                "paths_list": [],
                "mtime": 1.0,
                "size": 1,
                "type": "text/plain",
                "copies": 0,
                "version": 1,
                "next": "",
            }
            docs_by_id[doc_id] = doc
        doc["paths"][doc_relpath] = 1.0
        doc["paths_list"].append(doc_relpath)
        doc["copies"] = len(doc["paths"])
        if next_map and doc_relpath in next_map:
            doc["next"] = next_map[doc_relpath]

    for doc_id, doc in docs_by_id.items():
        doc_dir = by_id / str(doc_id)
        doc_dir.mkdir(exist_ok=True)
        (doc_dir / "document.json").write_text(json.dumps(doc))
        for relpath in doc["paths_list"]:
            link = by_path / Path(relpath)
            link.parent.mkdir(parents=True, exist_ok=True)
            relative_target = os.path.relpath(by_id / str(doc_id), link.parent)
            if link.is_symlink():
                link.unlink()
            link.symlink_to(relative_target, target_is_directory=True)

    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    by_id_dir = output_dir / "metadata" / "by-id"
    wait_for(
        lambda: by_id_dir.exists() and any(by_id_dir.iterdir()),
        message="metadata",
    )

    for doc_id in doc_ids:
        search_meili(compose_file, workdir, f'id = "{doc_id}"')

    return doc_ids


def _compose_paths() -> tuple[Path, Path, Path]:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    return compose_file, workdir, output_dir


def _run_sync(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    doc_ids: list[str],
    *,
    env_file: Path | None = None,
) -> None:
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    by_id_dir = output_dir / "metadata" / "by-id"
    wait_for(
        lambda: all((by_id_dir / did).exists() for did in doc_ids),
        message="metadata",
    )
    for doc_id in doc_ids:
        search_meili(compose_file, workdir, f'id = "{doc_id}"')
    compose(
        compose_file,
        workdir,
        "down",
        "--volumes",
        "--rmi",
        "local",
        env_file=env_file,
        check=False,
    )


def test_s1_drive_online(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (drive / "foo.txt").write_text("hi")

    try:
        ids = _run_once(
            compose_file, workdir, output_dir, ["archive/drive1/foo.txt"], setup
        )
        file_id = ids[0]
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        assert marker.exists()
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all(not doc["offline"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s2_drive_unplugged(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    ts = "2025-01-01T00:00:00Z"

    def setup(input_dir: Path) -> None:
        archive = input_dir / "archive"
        archive.mkdir()
        (archive / "drive1-status-ready").write_text(ts)

    try:
        file_id = "hash1"
        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/foo.txt"],
            setup,
            override_ids={"archive/drive1/foo.txt": file_id},
        )
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        assert marker.read_text() == ts
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all(doc["offline"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s3_drive_reattach_with_file(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    ts = "2025-01-01T00:00:00Z"

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (drive / "foo.txt").write_text("hi")
        (input_dir / "archive" / "drive1-status-ready").write_text(ts)

    try:
        file_id = "hash1"
        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/foo.txt"],
            setup,
            override_ids={"archive/drive1/foo.txt": file_id},
        )
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        ts_new = marker.read_text()
        assert ts_new != ts
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all(not doc["offline"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s4_drive_reattach_without_file(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    ts = "2025-01-01T00:00:00Z"

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (input_dir / "archive" / "drive1-status-ready").write_text(ts)

    try:
        file_id = "hash1"
        _run_once(
            compose_file,
            workdir,
            output_dir,
            [],
            setup,
        )
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        ts_new = marker.read_text()
        assert ts_new != ts
        with pytest.raises(AssertionError):
            search_meili(compose_file, workdir, f'id = "{file_id}"', timeout=5)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s5_file_copied_online(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (drive / "bar.txt").write_text("hi")

    try:
        ids = _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/bar.txt"],
            setup,
            next_map={"archive/drive1/bar.txt": "mod"},
        )
        file_id = ids[0]
        ready = workdir / "input" / "archive" / "drive1-status-ready"
        pending = workdir / "input" / "archive" / "drive1-status-pending"
        assert pending.exists()
        assert not ready.exists()
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all(not doc["offline"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s6_file_exists_on_both_paths(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (drive / "baz.txt").write_text("hi")
        (input_dir / "baz.txt").write_text("hi")

    try:
        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/baz.txt", "baz.txt"],
            setup,
        )
        doc_id = duplicate_finder.compute_hash(workdir / "input" / "baz.txt")
        by_id = output_dir / "metadata" / "by-id" / doc_id
        assert by_id.exists()
        docs = search_meili(compose_file, workdir, f'id = "{doc_id}"')
        assert all(not doc["offline"] for doc in docs)
        ready = workdir / "input" / "archive" / "drive1-status-ready"
        assert ready.exists()
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s7_online_copy_deleted_archive_offline(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    ts = "2025-01-01T00:00:00Z"

    def setup(input_dir: Path) -> None:
        archive_dir = input_dir / "archive"
        archive_dir.mkdir()
        (archive_dir / "drive1-status-ready").write_text(ts)
        doc_dir = output_dir / "metadata" / "by-id" / "hash1"
        doc_dir.mkdir(parents=True)
        doc = {
            "id": "hash1",
            "paths": {"archive/drive1/baz.txt": 1.0, "baz.txt": 1.0},
            "paths_list": ["archive/drive1/baz.txt", "baz.txt"],
            "mtime": 1.0,
            "size": 1,
            "type": "text/plain",
            "copies": 2,
            "version": 1,
            "next": "",
        }
        (doc_dir / "document.json").write_text(json.dumps(doc))
        link = output_dir / "metadata" / "by-path" / "archive" / "drive1" / "baz.txt"
        link.parent.mkdir(parents=True, exist_ok=True)
        relative_target = os.path.relpath(doc_dir, link.parent)
        link.symlink_to(relative_target, target_is_directory=True)
        link2 = output_dir / "metadata" / "by-path" / "baz.txt"
        link2.parent.mkdir(parents=True, exist_ok=True)
        relative_target2 = os.path.relpath(doc_dir, link2.parent)
        link2.symlink_to(relative_target2, target_is_directory=True)

    try:
        _run_once(
            compose_file,
            workdir,
            output_dir,
            [],
            setup,
            override_ids={},
        )
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        assert marker.read_text() == ts
        docs = search_meili(compose_file, workdir, 'id = "hash1"')
        assert all(doc["offline"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s8_archive_drive_renamed(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()

    def setup(input_dir: Path) -> None:
        archive = input_dir / "archive"
        archive.mkdir()
        (archive / "drive1-status-ready").write_text("old")
        drive = input_dir / "archive" / "drive2"
        drive.mkdir(parents=True)
        (drive / "foo.txt").write_text("hi")

    try:
        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive2/foo.txt"],
            setup,
            override_ids={"archive/drive2/foo.txt": "hash1"},
        )
        old_marker = workdir / "input" / "archive" / "drive1-status-ready"
        new_marker = workdir / "input" / "archive" / "drive2-status-ready"
        assert not old_marker.exists()
        assert new_marker.exists()
        link = output_dir / "metadata" / "by-path" / "archive" / "drive2" / "foo.txt"
        assert link.is_symlink()
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s9_multiple_drives_independent(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()

    def setup(input_dir: Path) -> None:
        drive1 = input_dir / "archive" / "drive1"
        drive1.mkdir(parents=True)
        (drive1 / "a.txt").write_text("a")
        archive = input_dir / "archive"
        (archive / "drive2-status-ready").write_text("old")

    try:
        ids = _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/a.txt", "archive/drive2/b.txt"],
            setup,
            override_ids={"archive/drive2/b.txt": "hash2"},
        )
        id1 = ids[0]
        id2 = "hash2"
        ready1 = workdir / "input" / "archive" / "drive1-status-ready"
        ready2 = workdir / "input" / "archive" / "drive2-status-ready"
        assert ready1.exists()
        assert ready2.read_text() == "old"
        docs1 = search_meili(compose_file, workdir, f'id = "{id1}"')
        docs2 = search_meili(compose_file, workdir, f'id = "{id2}"')
        assert all(not doc["offline"] for doc in docs1)
        assert all(doc["offline"] for doc in docs2)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s10_archive_directory_changed(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (drive / "foo.txt").write_text("hi")

    try:
        ids = _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/foo.txt"],
            setup,
        )
        file_id = ids[0]

        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )

        input_dir = workdir / "input"
        (input_dir / "archive").rename(input_dir / "archive2")
        env_file = tmp_path / ".env"
        env_file.write_text("ARCHIVE_DIRECTORY=/files/archive2\n")

        _run_sync(
            compose_file,
            workdir,
            output_dir,
            [file_id],
            env_file=env_file,
        )

        new_link = (
            output_dir / "metadata" / "by-path" / "archive2" / "drive1" / "foo.txt"
        )
        old_link = (
            output_dir / "metadata" / "by-path" / "archive" / "drive1" / "foo.txt"
        )
        assert new_link.is_symlink()
        assert not old_link.exists()
        marker = workdir / "input" / "archive2" / "drive1-status-ready"
        assert marker.exists()
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all(not doc["offline"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )


def test_s11_status_files_ignored(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()

    def setup(input_dir: Path) -> None:
        archive = input_dir / "archive"
        archive.mkdir()
        (archive / "Foo-status-ready").write_text("x")

    try:
        _run_once(compose_file, workdir, output_dir, [], setup)
        with pytest.raises(AssertionError):
            search_meili(
                compose_file,
                workdir,
                'paths_list = "archive/Foo-status-ready"',
                timeout=5,
            )
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
