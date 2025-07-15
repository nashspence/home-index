import json
import urllib.request
from pathlib import Path
from typing import Any

from features.F2 import duplicate_finder
from shared import compose, dump_logs, search_meili, wait_for


def _api_ready() -> bool:
    try:
        urllib.request.urlopen("http://localhost:8000/fileops")
    except urllib.error.HTTPError as e:
        return e.code == 405
    except Exception:
        return False
    return True


def _post_ops(data: dict[str, Any]) -> None:
    req = urllib.request.Request(
        "http://localhost:8000/fileops",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)


def _put_file(local: Path, remote: str) -> None:
    req = urllib.request.Request(
        f"http://localhost:8000/dav/{remote}",
        data=local.read_bytes(),
        method="PUT",
        headers={"Content-Type": "application/octet-stream"},
    )
    urllib.request.urlopen(req)


def test_file_ops_endpoint(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        wait_for(_api_ready, message="api start")
        file_a = tmp_path / "a.txt"
        text_a = b"hello"
        file_a.write_bytes(text_a)
        _put_file(file_a, "a.txt")
        file_id = duplicate_finder.compute_hash(file_a)
        doc_dir = output_dir / "metadata" / "by-id" / file_id
        wait_for(doc_dir.exists, message="metadata")
        wait_for(
            lambda: bool(search_meili(compose_file, workdir, f'id = "{file_id}"')),
            message="search add",
        )

        _post_ops({"move": [{"src": "a.txt", "dest": "b.txt"}]})

        def _moved() -> bool:
            with open(doc_dir / "document.json") as fh:
                doc = json.load(fh)
            return "b.txt" in doc.get("paths", {})

        wait_for(_moved, message="moved path")

        _post_ops({"delete": ["b.txt"]})
        wait_for(lambda: not doc_dir.exists(), message="deleted")
        wait_for(
            lambda: not search_meili(compose_file, workdir, f'id = "{file_id}"'),
            message="search delete",
        )

        file_c = tmp_path / "c.txt"
        file_d = tmp_path / "d.txt"
        file_c.write_text("c")
        file_d.write_text("d")
        _put_file(file_c, "c.txt")
        _put_file(file_d, "d.txt")
        _post_ops({"move": [{"src": "c.txt", "dest": "e.txt"}], "delete": ["d.txt"]})
        file_c_id = duplicate_finder.compute_hash(file_c)
        doc_c = output_dir / "metadata" / "by-id" / file_c_id / "document.json"
        wait_for(doc_c.exists, message="batch add")
        with open(doc_c) as fh:
            doc = json.load(fh)
        assert "e.txt" in doc.get("paths", {})
        wait_for(
            lambda: bool(search_meili(compose_file, workdir, f'id = "{file_c_id}"')),
            message="search batch",
        )
        wait_for(
            lambda: not search_meili(compose_file, workdir, 'paths = "d.txt"'),
            message="batch delete",
        )
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
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
