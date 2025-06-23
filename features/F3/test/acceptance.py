import json
import shutil
import subprocess
import time
from pathlib import Path


def _run_once(compose_file: Path, workdir: Path, output_dir: Path) -> tuple[Path, Path]:
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
        by_path_dir = output_dir / "metadata" / "by-path"
        return by_id_dir, by_path_dir
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


def test_paths_linked_to_metadata(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    by_id_dir, by_path_dir = _run_once(compose_file, workdir, output_dir)
    for doc_dir in [d for d in by_id_dir.iterdir() if d.is_dir()]:
        doc = json.loads((doc_dir / "document.json").read_text())
        for relpath in doc["paths"].keys():
            link = by_path_dir / relpath
            assert link.is_symlink()
            assert link.resolve() == doc_dir.resolve()
