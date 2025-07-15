import json
import os
import shutil
from pathlib import Path

import subprocess
import time

from shared import compose, dump_logs, search_meili, wait_for
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
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')

    env_file.write_text(f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\n")

    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    doc_id = _get_doc_id(workdir, output_dir)
    module_version = (
        output_dir / "metadata" / "by-id" / doc_id / "example-module" / "version.json"
    )
    try:
        wait_for(
            module_version.exists,
            timeout=300,
            message="module output",
        )
        docs = search_meili(compose_file, workdir, f'id = "{doc_id}"', timeout=300)
        assert any(doc["id"] == doc_id for doc in docs)
        data = json.loads(module_version.read_text())
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


def test_modules_process_documents(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)


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

    doc_id = _get_doc_id(workdir, output_dir)
    log_file = output_dir / "metadata" / "by-id" / doc_id / "timeout-module" / "log.txt"
    wait_for(log_file.exists, timeout=120, message="timeout log")
    wait_for(
        lambda: _redis_llen(compose_file, workdir, "timeout-module:run:processing") > 0,
        timeout=60,
        message="module started",
    )
    wait_for(
        lambda: _redis_llen(compose_file, workdir, "timeout-module:run") == 1,
        timeout=120,
        message="requeued",
    )
    time.sleep(2)
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
        output_dir / "metadata" / "by-id" / doc_id / "timeout-module" / "version.json"
    )
    wait_for(version_file.exists, timeout=300, message="module output")
    logs = log_file.read_text().splitlines()
    assert sum(1 for line in logs if "start" in line) >= 2
    docs = search_meili(compose_file, workdir, f'id = "{doc_id}"', timeout=300)
    assert any(doc["id"] == doc_id for doc in docs)

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

    doc_id = _get_doc_id(workdir, output_dir)

    wait_for(
        lambda: _redis_llen(compose_file, workdir, "timeout-module:check:processing")
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
        output_dir / "metadata" / "by-id" / doc_id / "timeout-module" / "version.json"
    )
    wait_for(version_file.exists, timeout=300, message="module output")

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


def test_module_timeouts(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    _run_timeout(compose_file, workdir, output_dir, env_file)


def test_module_check_timeouts(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    _run_check_timeout(compose_file, workdir, output_dir, env_file)
