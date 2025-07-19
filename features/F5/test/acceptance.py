import json
import os
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from features.F2 import duplicate_finder
from shared import compose, dump_logs, search_chunks, search_meili, wait_for


# utilities ---------------------------------------------------------------


def _compose_paths() -> tuple[Path, Path, Path]:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    return compose_file, workdir, output_dir


def _write_env(env_file: Path, extra: dict[str, str] | None = None) -> None:
    entries = [
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}",
        f"MODULE_BASE_IMAGE={os.environ.get('MODULE_BASE_IMAGE', 'home-index-module:ci')}",
    ]
    if extra:
        entries.extend(f"{k}={v}" for k, v in extra.items())
    env_file.write_text("\n".join(entries) + "\n")


def _start(compose_file: Path, workdir: Path, env_file: Path) -> None:
    compose(compose_file, workdir, "up", "-d", env_file=env_file)


def _stop(compose_file: Path, workdir: Path, env_file: Path) -> None:
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


def _prepare_dirs(workdir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "modules_config.json").write_text(
        '{"modules": [{"name": "text-module"}]}'
    )


# extended search helper -------------------------------------------------


def _search_chunks_custom(
    query: str,
    *,
    filter_expr: str = "",
    sort: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    timeout: int = 300,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    url = "http://localhost:7700/indexes/file_chunks/search"
    while True:
        try:
            data: dict[str, Any] = {
                "q": f"query: {query}",
                "hybrid": {"semanticRatio": 1, "embedder": "e5-small"},
            }
            if filter_expr:
                data["filter"] = filter_expr
            if sort:
                data["sort"] = [sort]
            if limit is not None:
                data["limit"] = limit
            if offset is not None:
                data["offset"] = offset
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                payload = json.load(resp)
            docs = payload.get("hits") or payload.get("results") or []
            if docs:
                return list(docs)
        except Exception:
            pass
        if time.time() > deadline:
            raise AssertionError("Timed out waiting for search results")
        time.sleep(0.5)


# scenario helpers -------------------------------------------------------


def _wait_initial(
    compose_file: Path, workdir: Path, doc_id: str, env_file: Path
) -> Path:
    module = "text-module"
    chunk_file = (
        workdir / "output" / "metadata" / "by-id" / doc_id / module / "chunks.json"
    )
    content_file = chunk_file.with_name("content.json")
    wait_for(chunk_file.exists, timeout=300, message="chunks")
    wait_for(content_file.exists, timeout=300, message="content")
    wait_for(
        lambda: bool(search_meili(compose_file, workdir, f'id = "{doc_id}"')),
        timeout=300,
        message="indexed",
    )
    return chunk_file


# scenarios ---------------------------------------------------------------


def test_s1_initial_build(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        _wait_initial(compose_file, workdir, doc_id, env_file)
        results = search_chunks(
            "automatic learning from data",
            filter_expr=f'file_id = "{doc_id}"',
        )
        assert any(r["file_id"] == doc_id for r in results)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s2_new_file_added(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        _wait_initial(compose_file, workdir, doc_id, env_file)
        new_file = workdir / "input" / "extra.txt"
        new_file.write_text("extra content for scenario two")
        new_id = duplicate_finder.compute_hash(new_file)
        new_chunk = (
            output_dir / "metadata" / "by-id" / new_id / "text-module" / "chunks.json"
        )
        wait_for(new_chunk.exists, timeout=300, message="new chunks")
        results = search_chunks(
            "extra content",
            filter_expr=f'file_id = "{new_id}"',
        )
        assert any(r["file_id"] == new_id for r in results)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s3_file_contents_change(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    orig_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        _wait_initial(compose_file, workdir, orig_id, env_file)
        doc_path.write_text("changed text for scenario three")
        new_id = duplicate_finder.compute_hash(doc_path)
        new_chunk = (
            output_dir / "metadata" / "by-id" / new_id / "text-module" / "chunks.json"
        )
        wait_for(new_chunk.exists, timeout=300, message="new chunks")
        assert (output_dir / "metadata" / "by-id" / orig_id).exists()
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s4_chunk_schema_complete(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        chunk_file = _wait_initial(compose_file, workdir, doc_id, env_file)
        chunks = json.loads(chunk_file.read_text())
        required = {
            "id",
            "file_id",
            "module",
            "text",
            "index",
            "char_offset",
            "char_length",
        }
        for c in chunks:
            assert required <= set(c)
            assert all(c[f] is not None for f in required)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s5_sorted_paged_search(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file, {"TOKENS_PER_CHUNK": "20", "CHUNK_OVERLAP": "0"})

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        _wait_initial(compose_file, workdir, doc_id, env_file)
        results = _search_chunks_custom(
            "learning from data",
            filter_expr=f'file_id = "{doc_id}"',
            sort="index:asc",
            limit=3,
            offset=2,
        )
        indexes = [r["index"] for r in results]
        assert indexes == sorted(indexes)
        assert indexes[0] >= 2
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s6_chunk_size_change_triggers_rebuild(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file, {"TOKENS_PER_CHUNK": "1000", "CHUNK_OVERLAP": "0"})

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        chunk_file = _wait_initial(compose_file, workdir, doc_id, env_file)
        mtime1 = chunk_file.stat().st_mtime
        content1 = chunk_file.with_name("content.json").read_text()
        log_file = chunk_file.with_name("log.txt")
        start_count1 = log_file.read_text().count("start")
        settings1 = json.loads((output_dir / "chunk_settings.json").read_text())
        assert settings1["TOKENS_PER_CHUNK"] == 1000
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)

    _write_env(env_file, {"TOKENS_PER_CHUNK": "10", "CHUNK_OVERLAP": "0"})
    _start(compose_file, workdir, env_file)
    try:
        chunk_file = _wait_initial(compose_file, workdir, doc_id, env_file)
        assert chunk_file.stat().st_mtime > mtime1
        chunks = json.loads(chunk_file.read_text())
        assert len(chunks) > 1
        assert chunk_file.with_name("content.json").read_text() == content1
        log_file = chunk_file.with_name("log.txt")
        assert log_file.read_text().count("start") == start_count1
        settings2 = json.loads((output_dir / "chunk_settings.json").read_text())
        assert settings2["TOKENS_PER_CHUNK"] == 10
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s7_model_change_reembeds_only(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file, {"EMBED_MODEL_NAME": "intfloat/e5-small-v2"})

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        chunk_file = _wait_initial(compose_file, workdir, doc_id, env_file)
        mtime1 = chunk_file.stat().st_mtime
        content = chunk_file.with_name("content.json").read_text()
        log_file = chunk_file.with_name("log.txt")
        start_count1 = log_file.read_text().count("start")
        settings1 = json.loads((output_dir / "chunk_settings.json").read_text())
        assert settings1["EMBED_MODEL_NAME"] == "intfloat/e5-small-v2"
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)

    _write_env(env_file, {"EMBED_MODEL_NAME": "intfloat/e5-base"})
    _start(compose_file, workdir, env_file)
    try:
        chunk_file = _wait_initial(compose_file, workdir, doc_id, env_file)
        assert chunk_file.stat().st_mtime > mtime1
        assert chunk_file.with_name("content.json").read_text() == content
        log_file = chunk_file.with_name("log.txt")
        assert log_file.read_text().count("start") == start_count1
        settings2 = json.loads((output_dir / "chunk_settings.json").read_text())
        assert settings2["EMBED_MODEL_NAME"] == "intfloat/e5-base"
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s8_warm_restart_no_change(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        chunk_file = _wait_initial(compose_file, workdir, doc_id, env_file)
        mtime1 = chunk_file.stat().st_mtime
        log_file = chunk_file.with_name("log.txt")
        start_count1 = log_file.read_text().count("start")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)

    time.sleep(1)
    _write_env(env_file)
    _start(compose_file, workdir, env_file)
    try:
        chunk_file = _wait_initial(compose_file, workdir, doc_id, env_file)
        assert chunk_file.stat().st_mtime == mtime1
        log_file = chunk_file.with_name("log.txt")
        assert log_file.read_text().count("start") == start_count1
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s9_deletion_reflected(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        _wait_initial(compose_file, workdir, doc_id, env_file)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)

    doc_path.unlink()
    _write_env(env_file)
    _start(compose_file, workdir, env_file)
    try:
        with pytest.raises(AssertionError):
            search_meili(compose_file, workdir, f'id = "{doc_id}"', timeout=5)
        metadata_dir = output_dir / "metadata" / "by-id" / doc_id
        wait_for(lambda: not metadata_dir.exists(), message="metadata removed")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)


def test_s10_hybrid_filter(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = _compose_paths()
    env_file = tmp_path / ".env"
    _prepare_dirs(workdir, output_dir)
    _write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    _start(compose_file, workdir, env_file)
    try:
        _wait_initial(compose_file, workdir, doc_id, env_file)
        results = _search_chunks_custom(
            "learning from data",
            filter_expr="module = 'text-module'",
        )
        assert results and all(r["module"] == "text-module" for r in results)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        _stop(compose_file, workdir, env_file)
