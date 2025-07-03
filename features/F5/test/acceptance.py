import json
import shutil
import urllib.request
from pathlib import Path

from features.F2 import duplicate_finder
from shared import compose, dump_logs, search_chunks, wait_for


def _run_once(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text(
        '{"modules": [{"name": "chunk-module"}]}'
    )

    env_file.write_text("")

    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)
    from features.F5 import chunk_utils

    chunk_json = (
        output_dir
        / "metadata"
        / "by-id"
        / doc_id
        / "chunk-module"
        / chunk_utils.CHUNK_FILENAME
    )
    try:
        wait_for(
            chunk_json.exists,
            timeout=300,
            message="chunk metadata",
        )

        with open(chunk_json) as fh:
            chunks = json.load(fh)

        chunk_ids = {c["id"] for c in chunks}
        chunk = next(c for c in chunks if c["id"] == f"chunk_module_{doc_id}_0")
        for field in ["id", "file_id", "module", "text", "index"]:
            assert field in chunk

        queries = [
            "algorithms that learn from data",
            "automatic learning from data",
        ]
        for query in queries:
            results = search_chunks(query, filter_expr=f'file_id = "{doc_id}"')
            assert any(r["id"] in chunk_ids for r in results)
            doc = next(r for r in results if r["id"] == f"chunk_module_{doc_id}_0")
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


def test_search_file_chunks_by_concept(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)
