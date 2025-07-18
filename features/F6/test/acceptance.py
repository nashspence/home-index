import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from features.F2 import duplicate_finder
from shared import compose, dump_logs, search_meili, wait_for

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


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


def _move_dav(src: str, dest: str) -> None:
    req = urllib.request.Request(
        f"http://localhost:8000/dav/{src}",
        method="MOVE",
        headers={"Destination": f"http://localhost:8000/dav/{dest}"},
    )
    urllib.request.urlopen(req)


def _compose_paths() -> tuple[Path, Path, Path]:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    return compose_file, workdir, output_dir


def _start_stack(
    compose_file: Path, workdir: Path, output_dir: Path, env_file: Path
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')
    input_dir = workdir / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir()
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    wait_for(_api_ready, message="api start")


def _stop_stack(compose_file: Path, workdir: Path, env_file: Path) -> None:
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


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


def test_s1_add_file(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _start_stack(compose_file, workdir, output_dir, env_file)
    try:
        file_a = tmp_path / "a.txt"
        file_a.write_text("hello")
        _put_file(file_a, "a.txt")
        file_id = duplicate_finder.compute_hash(file_a)
        doc_dir = output_dir / "metadata" / "by-id" / file_id
        wait_for(doc_dir.exists, message="metadata")
        wait_for(
            lambda: bool(search_meili(compose_file, workdir, f'id = "{file_id}"')),
            message="search add",
        )
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop_stack(compose_file, workdir, env_file)


def test_s2_move_file_json(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _start_stack(compose_file, workdir, output_dir, env_file)
    try:
        file_a = tmp_path / "a.txt"
        file_a.write_text("hello")
        _put_file(file_a, "a.txt")
        file_id = duplicate_finder.compute_hash(file_a)
        doc_dir = output_dir / "metadata" / "by-id" / file_id
        wait_for(doc_dir.exists, message="metadata")
        _post_ops({"move": [{"src": "a.txt", "dest": "b.txt"}]})

        def _moved() -> bool:
            with open(doc_dir / "document.json") as fh:
                doc = json.load(fh)
            return "b.txt" in doc.get("paths", {}) and "a.txt" not in doc.get(
                "paths", {}
            )

        wait_for(_moved, message="moved path")
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all(
            "b.txt" in doc["paths"] and "a.txt" not in doc["paths"] for doc in docs
        )
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop_stack(compose_file, workdir, env_file)


def test_s3_delete_file(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _start_stack(compose_file, workdir, output_dir, env_file)
    try:
        file_a = tmp_path / "a.txt"
        file_a.write_text("hello")
        _put_file(file_a, "a.txt")
        file_id = duplicate_finder.compute_hash(file_a)
        doc_dir = output_dir / "metadata" / "by-id" / file_id
        wait_for(doc_dir.exists, message="metadata")
        _post_ops({"move": [{"src": "a.txt", "dest": "b.txt"}]})
        wait_for(lambda: (doc_dir / "document.json").exists(), message="moved")
        _post_ops({"delete": ["b.txt"]})
        wait_for(lambda: not doc_dir.exists(), message="deleted")

        def _deleted() -> bool:
            try:
                search_meili(compose_file, workdir, f'id = "{file_id}"', timeout=1)
            except AssertionError:
                return True
            return False

        wait_for(_deleted, message="search delete")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop_stack(compose_file, workdir, env_file)


def test_s4_batch_operations(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _start_stack(compose_file, workdir, output_dir, env_file)
    try:
        file_c = tmp_path / "c.txt"
        file_d = tmp_path / "d.txt"
        file_c.write_text("c")
        file_d.write_text("d")
        _put_file(file_c, "c.txt")
        _put_file(file_d, "d.txt")
        file_c_id = duplicate_finder.compute_hash(file_c)
        file_d_id = duplicate_finder.compute_hash(file_d)
        doc_c = output_dir / "metadata" / "by-id" / file_c_id
        doc_d = output_dir / "metadata" / "by-id" / file_d_id
        wait_for(doc_c.exists, message="metadata c")
        wait_for(doc_d.exists, message="metadata d")
        _post_ops({"move": [{"src": "c.txt", "dest": "e.txt"}], "delete": ["d.txt"]})

        def _moved() -> bool:
            with open(doc_c / "document.json") as fh:
                doc = json.load(fh)
            return "e.txt" in doc.get("paths", {})

        wait_for(_moved, message="moved c")
        wait_for(lambda: not doc_d.exists(), message="deleted d")
        wait_for(
            lambda: bool(search_meili(compose_file, workdir, f'id = "{file_c_id}"')),
            message="search c",
        )

        def _gone() -> bool:
            try:
                search_meili(compose_file, workdir, f'id = "{file_d_id}"', timeout=1)
            except AssertionError:
                return True
            return False

        wait_for(_gone, message="search d")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop_stack(compose_file, workdir, env_file)


def test_s5_rename_via_webdav(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _start_stack(compose_file, workdir, output_dir, env_file)
    try:
        file_e = tmp_path / "e.txt"
        file_e.write_text("e")
        _put_file(file_e, "e.txt")
        file_id = duplicate_finder.compute_hash(file_e)
        doc_dir = output_dir / "metadata" / "by-id" / file_id
        wait_for(doc_dir.exists, message="metadata")
        _move_dav("e.txt", "f.txt")

        def _moved() -> bool:
            with open(doc_dir / "document.json") as fh:
                doc = json.load(fh)
            return "f.txt" in doc.get("paths", {}) and "e.txt" not in doc.get(
                "paths", {}
            )

        wait_for(_moved, message="moved via DAV")
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all("f.txt" in doc["paths"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop_stack(compose_file, workdir, env_file)
