from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from shared import compose, wait_for


def api_ready() -> bool:
    try:
        urllib.request.urlopen("http://localhost:8000/fileops")
    except urllib.error.HTTPError as e:
        return e.code == 405
    except Exception:
        return False
    return True


def post_ops(data: dict[str, Any]) -> None:
    req = urllib.request.Request(
        "http://localhost:8000/fileops",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)


def put_file(local: Path, remote: str) -> None:
    req = urllib.request.Request(
        f"http://localhost:8000/dav/{remote}",
        data=local.read_bytes(),
        method="PUT",
        headers={"Content-Type": "application/octet-stream"},
    )
    urllib.request.urlopen(req)


def move_dav(src: str, dest: str) -> None:
    req = urllib.request.Request(
        f"http://localhost:8000/dav/{src}",
        method="MOVE",
        headers={"Destination": f"http://localhost:8000/dav/{dest}"},
    )
    urllib.request.urlopen(req)


def start(compose_file: Path, workdir: Path, output_dir: Path, env_file: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')
    input_dir = workdir / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir()
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    wait_for(api_ready, message="api start")


def stop(compose_file: Path, workdir: Path, env_file: Path) -> None:
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
