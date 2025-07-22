import json
import os
import shutil
import tempfile
from pathlib import Path

import subprocess
import time
import pytest

from shared import (
    compose,
    compose_paths,
    dump_logs,
    search_meili,
    wait_for,
)
from features.F2 import duplicate_finder


def _get_doc_id(workdir: Path, output_dir: Path, file_name: str = "hello.txt") -> str:
    """Return the expected document ID and wait for its metadata directory."""
    doc_path = workdir / "input" / file_name
    doc_id = duplicate_finder.compute_hash(doc_path)
    by_id = output_dir / "metadata" / "by-id" / doc_id
    wait_for(by_id.exists, message="metadata")
    return doc_id


def _run_once(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
    file_name: str = "hello.txt",
) -> None:
    _run_files(compose_file, workdir, output_dir, env_file, [file_name])


def _run_files(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
    file_names: list[str],
) -> list[Path]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')

    env_file.write_text(f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\n")

    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    doc_ids = [_get_doc_id(workdir, output_dir, name) for name in file_names]
    version_files = [
        output_dir / "metadata" / "by-id" / did / "example-module" / "version.json"
        for did in doc_ids
    ]
    try:
        for vf in version_files:
            wait_for(vf.exists, timeout=300, message="module output")
        for did in doc_ids:
            docs = search_meili(compose_file, workdir, f'id = "{did}"', timeout=300)
            assert any(doc["id"] == did for doc in docs)
        for vf in version_files:
            data = json.loads(vf.read_text())
            assert data.get("version") == 1
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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
    return version_files


def _run_again(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
) -> None:
    """Run the stack again without wiping ``output_dir``."""
    env_file.write_text(f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\n")
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _get_doc_id(workdir, output_dir)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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


def _run_add_module(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
) -> None:
    """Add ``timeout-module`` to the pipeline and run once."""
    (output_dir / "modules_config.json").write_text(
        '{"modules": [{"name": "timeout-module"}]}'
    )
    env_file.write_text(f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\n")
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        doc_id = _get_doc_id(workdir, output_dir)
        version_file = (
            output_dir
            / "metadata"
            / "by-id"
            / doc_id
            / "timeout-module"
            / "version.json"
        )
        wait_for(version_file.exists, timeout=300, message="module output")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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


def _run_remove_drive_mid(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
) -> tuple[str, str]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')
    env_file.write_text(
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\nMODULE_SLEEP=2\nUID_RETRY_SECONDS=1\n"
    )
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    doc_a = doc_b = ""
    try:
        doc_a = _get_doc_id(workdir, output_dir, "archive/drive1/a.txt")
        doc_b = _get_doc_id(workdir, output_dir, "archive/drive1/b.txt")
        wait_for(
            (
                output_dir
                / "metadata"
                / "by-id"
                / doc_a
                / "example-module"
                / "version.json"
            ).exists,
            timeout=300,
            message="module a",
        )
        shutil.rmtree(workdir / "input" / "archive" / "drive1")
        time.sleep(3)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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
    return doc_a, doc_b


def _run_uid_mismatch(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
) -> str:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')
    env_file.write_text(
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\nUID_RETRY_SECONDS=1\n"
    )
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    doc_id = ""
    try:
        doc_id = duplicate_finder.compute_hash(workdir / "input" / "hello.txt")
        bad = json.dumps({"id": doc_id, "paths": {"hello.txt": 1}, "uid": "bad"})
        _redis_cmd(compose_file, workdir, "RPUSH", "example-module:run", bad)
        wait_for(
            lambda: "uid mismatch"
            in _container_logs(compose_file, workdir, "example-module"),
            timeout=60,
            message="uid warning",
        )
        count = _redis_llen(compose_file, workdir, "example-module:run")
        assert count == 1
        good = json.dumps(
            {
                "id": doc_id,
                "paths": {"hello.txt": 1},
                "uid": "00000000-0000-0000-0000-000000000001",
            }
        )
        _redis_cmd(compose_file, workdir, "RPUSH", "example-module:run", good)
        version_file = (
            output_dir
            / "metadata"
            / "by-id"
            / doc_id
            / "example-module"
            / "version.json"
        )
        wait_for(version_file.exists, timeout=300, message="module output")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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
    return doc_id


def _run_crash_isolation(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
) -> tuple[str, str]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')
    env_file.write_text(
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\n"
        "EXAMPLE_RESOURCE_SHARES=- name: gpu\\n  seconds: 1\n"
        "CRASH_RESOURCE_SHARES=- name: gpu\\n  seconds: 1\n"
        "EXAMPLE_WORKER_ID=worker1\nCRASH_WORKER_ID=worker2\n"
        "CRASH=1\nEXAMPLE_TIMEOUT=1\nCRASH_TIMEOUT=1\n"
    )
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    doc_id = ""
    logs = ""
    try:
        doc_id = duplicate_finder.compute_hash(workdir / "input" / "hello.txt")
        job = json.dumps(
            {
                "id": doc_id,
                "paths": {"hello.txt": 1},
                "uid": "00000000-0000-0000-0000-000000000003",
            }
        )
        _redis_cmd(compose_file, workdir, "RPUSH", "crash-module:run", job)
        version_file = (
            output_dir
            / "metadata"
            / "by-id"
            / doc_id
            / "example-module"
            / "version.json"
        )
        wait_for(version_file.exists, timeout=300, message="example output")
        wait_for(
            lambda: _container_status(compose_file, workdir, "crash-module")
            == "exited",
            timeout=60,
            message="crash exit",
        )
        logs = _container_logs(compose_file, workdir, "crash-module")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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
    return doc_id, logs


def _run_share_group_rotation(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
) -> tuple[str, str]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')
    env_file.write_text(
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\n"
        "EXAMPLE_RESOURCE_SHARES=- name: gpu\\n  seconds: 1\n"
        "EXAMPLE_WORKER_ID=worker1\n"
        "TIMEOUT_RESOURCE_SHARES=- name: gpu\\n  seconds: 1\\n- name: licence\\n  seconds: 1\n"
        "TIMEOUT_WORKER_ID=worker2\n"
        "EXAMPLE_TIMEOUT=1\nTIMEOUT_TIMEOUT=1\n"
    )
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    logs_example = ""
    logs_timeout = ""
    try:
        doc_id = duplicate_finder.compute_hash(workdir / "input" / "hello.txt")
        job = json.dumps(
            {
                "id": doc_id,
                "paths": {"hello.txt": 1},
                "uid": "00000000-0000-0000-0000-000000000002",
            }
        )
        _redis_cmd(compose_file, workdir, "RPUSH", "timeout-module:run", job)
        job2 = json.dumps(
            {
                "id": doc_id,
                "paths": {"hello.txt": 1},
                "uid": "00000000-0000-0000-0000-000000000001",
            }
        )
        _redis_cmd(compose_file, workdir, "RPUSH", "example-module:run", job2)
        version_timeout = (
            output_dir
            / "metadata"
            / "by-id"
            / doc_id
            / "timeout-module"
            / "version.json"
        )
        version_example = (
            output_dir
            / "metadata"
            / "by-id"
            / doc_id
            / "example-module"
            / "version.json"
        )
        wait_for(version_example.exists, timeout=300, message="example output")
        wait_for(version_timeout.exists, timeout=300, message="timeout output")
        logs_example = _container_logs(compose_file, workdir, "example-module")
        logs_timeout = _container_logs(compose_file, workdir, "timeout-module")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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
    return logs_example, logs_timeout


def test_s1_initial_enrichment(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    drive = workdir / "input" / "archive" / "drive1"
    drive.mkdir(parents=True)
    (drive / "foo.txt").write_text("hi")
    (workdir / "input" / "archive" / "drive1-status-pending").write_text("x")
    _run_once(
        compose_file,
        workdir,
        output_dir,
        env_file,
        file_name="archive/drive1/foo.txt",
    )
    ready = workdir / "input" / "archive" / "drive1-status-ready"
    assert ready.exists()


def test_s2_plug_in_archive_drive(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    drive = workdir / "input" / "archive" / "drive1"
    drive.mkdir(parents=True)
    (drive / "foo.txt").write_text("hi")
    marker = workdir / "input" / "archive" / "drive1-status-ready"
    marker.write_text("old")
    _run_once(
        compose_file,
        workdir,
        output_dir,
        env_file,
        file_name="archive/drive1/foo.txt",
    )
    assert marker.read_text() != "old"


def test_s3_remove_drive_mid_run(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    drive = workdir / "input" / "archive" / "drive1"
    drive.mkdir(parents=True)
    (drive / "a.txt").write_text("a")
    (drive / "b.txt").write_text("b")
    marker_pending = workdir / "input" / "archive" / "drive1-status-pending"
    marker_pending.write_text("old")
    doc_a, doc_b = _run_remove_drive_mid(compose_file, workdir, output_dir, env_file)
    version_b = (
        output_dir / "metadata" / "by-id" / doc_b / "example-module" / "version.json"
    )
    assert not version_b.exists()
    assert marker_pending.exists()
    drive.mkdir(parents=True)
    (drive / "b.txt").write_text("b")
    _run_again(compose_file, workdir, output_dir, env_file)
    assert version_b.exists()
    ready = workdir / "input" / "archive" / "drive1-status-ready"
    assert ready.exists()


def test_s4_uid_order_change() -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_path = Path(tempfile.mkdtemp()) / ".env"
    _run_once(compose_file, workdir, output_dir, env_path)
    doc_id = _get_doc_id(workdir, output_dir)
    example_version = (
        output_dir / "metadata" / "by-id" / doc_id / "example-module" / "version.json"
    )
    mtime = example_version.stat().st_mtime
    _run_add_module(compose_file, workdir, output_dir, env_path)
    assert example_version.stat().st_mtime == mtime
    timeout_version = (
        output_dir / "metadata" / "by-id" / doc_id / "timeout-module" / "version.json"
    )
    assert timeout_version.exists()


def test_s5_status_files_ignored() -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    (workdir / "input" / "Foo-status-ready").write_text("x")
    env_file = Path(tempfile.mkdtemp()) / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)
    with pytest.raises(AssertionError):
        search_meili(
            compose_file, workdir, 'paths_list = "Foo-status-ready"', timeout=5
        )


def test_s6_non_archive_files_unaffected(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    drive = workdir / "input" / "archive" / "drive1"
    drive.mkdir(parents=True)
    (drive / "a.txt").write_text("a")
    regular = workdir / "input" / "b.txt"
    regular.write_text("b")
    marker = workdir / "input" / "archive" / "drive1-status-ready"
    marker.write_text("old")
    version_files = _run_files(
        compose_file,
        workdir,
        output_dir,
        env_file,
        ["archive/drive1/a.txt", "b.txt"],
    )
    archive_version = version_files[0]
    regular_version = version_files[1]
    assert regular_version.stat().st_mtime >= archive_version.stat().st_mtime
    assert marker.read_text() != "old"


def test_s7_legacy_docs_still_searchable(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)
    doc_id = _get_doc_id(workdir, output_dir)
    docs = search_meili(compose_file, workdir, f'id = "{doc_id}"')
    assert any(doc["id"] == doc_id for doc in docs)
    _run_add_module(compose_file, workdir, output_dir, env_file)
    docs_after = search_meili(compose_file, workdir, f'id = "{doc_id}"')
    assert any(doc["id"] == doc_id for doc in docs_after)


def _redis_llen(compose_file: Path, workdir: Path, key: str) -> int:
    output = subprocess.check_output(
        [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "exec",
            "-T",
            "redis",
            "redis-cli",
            "LLEN",
            key,
        ],
        cwd=workdir,
    )
    return int(output.decode().strip())


def _redis_cmd(compose_file: Path, workdir: Path, *args: str) -> str:
    output = subprocess.check_output(
        [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "exec",
            "-T",
            "redis",
            "redis-cli",
            *args,
        ],
        cwd=workdir,
    )
    return output.decode().strip()


def _container_logs(compose_file: Path, workdir: Path, service: str) -> str:
    return subprocess.check_output(
        ["docker", "compose", "-f", str(compose_file), "logs", service],
        cwd=workdir,
    ).decode()


def _container_status(compose_file: Path, workdir: Path, service: str) -> str:
    cid = (
        subprocess.check_output(
            ["docker", "compose", "-f", str(compose_file), "ps", "-q", service],
            cwd=workdir,
        )
        .decode()
        .strip()
    )
    if not cid:
        return "missing"
    return (
        subprocess.check_output(["docker", "inspect", "-f", "{{.State.Status}}", cid])
        .decode()
        .strip()
    )


def _run_timeout(
    compose_file: Path, workdir: Path, output_dir: Path, env_file: Path
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text(
        '{"modules": [{"name": "timeout-module"}]}'
    )

    env_file.write_text(
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\nTIMEOUT=1\nMODULE_SLEEP=2\n"
    )

    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        doc_id = _get_doc_id(workdir, output_dir)
        log_file = (
            output_dir / "metadata" / "by-id" / doc_id / "timeout-module" / "log.txt"
        )
        wait_for(log_file.exists, timeout=120, message="timeout log")
        # allow the job to time out
        wait_for(
            lambda: _redis_llen(compose_file, workdir, "modules:done") == 0,
            timeout=60,
            message="no done",
        )

        compose(compose_file, workdir, "stop", env_file=env_file, check=False)

        env_file.write_text(
            f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\nTIMEOUT=1\nMODULE_SLEEP=0\n"
        )
        compose(compose_file, workdir, "up", "-d", env_file=env_file)

        version_file = (
            output_dir
            / "metadata"
            / "by-id"
            / doc_id
            / "timeout-module"
            / "version.json"
        )
        wait_for(version_file.exists, timeout=300, message="module output")
        logs = log_file.read_text().splitlines()
        assert sum(1 for line in logs if "start" in line) >= 2
        docs = search_meili(compose_file, workdir, f'id = "{doc_id}"', timeout=300)
        assert any(doc["id"] == doc_id for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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


def _run_check_timeout(
    compose_file: Path, workdir: Path, output_dir: Path, env_file: Path
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text(
        '{"modules": [{"name": "timeout-module"}]}'
    )

    env_file.write_text(
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\nTIMEOUT=1\nCHECK_SLEEP=2\nMODULE_SLEEP=0\n"
    )

    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        doc_id = _get_doc_id(workdir, output_dir)

        wait_for(
            lambda: _redis_llen(
                compose_file, workdir, "timeout-module:check:processing"
            )
            > 0,
            timeout=60,
            message="processing",
        )
        wait_for(
            lambda: _redis_llen(compose_file, workdir, "timeout-module:check") == 1,
            timeout=120,
            message="requeued",
        )

        compose(compose_file, workdir, "stop", env_file=env_file, check=False)

        env_file.write_text(
            f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\nTIMEOUT=1\nCHECK_SLEEP=0\nMODULE_SLEEP=0\n"
        )
        compose(compose_file, workdir, "up", "-d", env_file=env_file)

        version_file = (
            output_dir
            / "metadata"
            / "by-id"
            / doc_id
            / "timeout-module"
            / "version.json"
        )
        wait_for(version_file.exists, timeout=300, message="module output")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(compose_file, workdir, "stop", env_file=env_file, check=False)
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
