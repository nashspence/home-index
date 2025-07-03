import json
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from features.F2 import duplicate_finder
from shared import compose, dump_logs, search_chunks, wait_for


def _run_once(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
    env: dict[str, str] | None = None,
    *,
    reset_output: bool = True,
) -> list[dict[str, Any]]:
    if reset_output and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "modules_config.json").write_text(
        '{"modules": [{"name": "chunk-module"}]}'
    )

    entries = [
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}",
        f"MODULE_BASE_IMAGE={os.environ.get('MODULE_BASE_IMAGE', 'home-index-module:ci')}",
    ]
    if env:
        entries.extend(f"{k}={v}" for k, v in env.items())
    env_file.write_text("\n".join(entries) + "\n")

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)
    from features.F5 import chunk_utils

    module_name = "chunk-module"
    chunk_json = (
        output_dir
        / "metadata"
        / "by-id"
        / doc_id
        / module_name
        / chunk_utils.CHUNK_FILENAME
    )
    if not reset_output and chunk_json.exists():
        chunk_json.unlink()

    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    chunks: list[dict[str, Any]] = []
    try:
        wait_for(
            chunk_json.exists,
            timeout=300,
            message="chunk metadata",
        )

        with open(chunk_json) as fh:
            chunks = json.load(fh)

        chunk_ids = {c["id"] for c in chunks}
        chunk = next(c for c in chunks if c["id"] == f"{module_name}_{doc_id}_0")
        for field in ["id", "file_id", "module", "text", "index"]:
            assert field in chunk

        queries = [
            "algorithms that learn from data",
            "automatic learning from data",
        ]
        for query in queries:
            results = search_chunks(query, filter_expr=f'file_id = "{doc_id}"')
            assert any(r["id"] in chunk_ids for r in results)
            doc = next(r for r in results if r["id"] == f"{module_name}_{doc_id}_0")
            for field in ["id", "file_id", "module", "text", "index"]:
                assert field in doc

        with urllib.request.urlopen(
            "http://localhost:7700/indexes/file_chunks/settings"
        ) as resp:
            settings = json.load(resp)
        assert "file_id" in settings.get("filterableAttributes", [])
        assert "module" in settings.get("filterableAttributes", [])
        assert "index" in settings.get("sortableAttributes", [])
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
    return chunks


def test_search_file_chunks_by_concept(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)


def test_chunk_settings_change(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"

    first_env = {"TOKENS_PER_CHUNK": "1000", "CHUNK_OVERLAP": "0"}
    chunks1 = _run_once(
        compose_file,
        workdir,
        output_dir,
        env_file,
        env=first_env,
    )
    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)
    settings_path = output_dir / "chunk_settings.json"
    with settings_path.open() as fh:
        settings1 = json.load(fh)
    assert settings1["TOKENS_PER_CHUNK"] == 1000
    assert len(chunks1) == 1

    module_dir = output_dir / "metadata" / "by-id" / doc_id / "chunk-module"
    chunk_file = module_dir / "chunks.json"
    log_file = module_dir / "log.txt"
    mtime1 = chunk_file.stat().st_mtime
    start_count1 = log_file.read_text().count("start")

    second_env = {"TOKENS_PER_CHUNK": "10", "CHUNK_OVERLAP": "0"}
    chunks2 = _run_once(
        compose_file,
        workdir,
        output_dir,
        env_file,
        env=second_env,
        reset_output=False,
    )
    with settings_path.open() as fh:
        settings2 = json.load(fh)

    assert settings2["TOKENS_PER_CHUNK"] == 10
    assert len(chunks2) > len(chunks1)
    mtime2 = chunk_file.stat().st_mtime
    start_count2 = log_file.read_text().count("start")

    assert mtime2 > mtime1
    assert start_count2 > start_count1
