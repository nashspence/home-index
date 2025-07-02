import json
import os
import shutil
from pathlib import Path

from shared import compose, dump_logs, search_meili, wait_for

from features.F2 import duplicate_finder


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
    doc_path = workdir / "input" / "hello.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)
    module_version = (
        output_dir / "metadata" / "by-id" / doc_id / "example_module" / "version.json"
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
