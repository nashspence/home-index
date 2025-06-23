import json
import shutil
import subprocess
import time
from pathlib import Path


def _run_once(compose_file: Path, workdir: Path, output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "up",
            "-d",
        ],
        check=True,
        cwd=workdir,
    )
    try:
        by_id_dir = output_dir / "metadata" / "by-id"
        deadline = time.time() + 60
        while True:
            time.sleep(0.5)
            if by_id_dir.exists() and any(by_id_dir.iterdir()):
                break
            if time.time() > deadline:
                raise AssertionError("Timed out waiting for metadata")
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "stop",
            ],
            check=True,
            cwd=workdir,
        )
        return by_id_dir
    except Exception:
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "logs",
                "--no-color",
            ],
            check=False,
            cwd=workdir,
        )
        if (output_dir / "files.log").exists():
            print("--- files.log ---")
            print((output_dir / "files.log").read_text())
        raise
    finally:
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "rm",
                "-fsv",
            ],
            check=False,
            cwd=workdir,
        )


def test_metadata_saved_by_id(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    by_id_dir = _run_once(compose_file, workdir, output_dir)
    subdirs = [d for d in by_id_dir.iterdir() if d.is_dir()]
    assert len(subdirs) >= 2
    docs = [json.loads((d / "document.json").read_text()) for d in subdirs]
    paths = {p for doc in docs for p in doc["paths"].keys()}
    assert "hello.txt" in paths
    assert "goodbye.txt" in paths
