import json
import importlib


def test_index_files_preserves_content(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    meta_dir = tmp_path / "meta"
    by_id = meta_dir / "by-id"
    by_path = meta_dir / "by-path"

    for d in [index_dir, meta_dir, by_id, by_path]:
        d.mkdir(parents=True, exist_ok=True)

    file_path = index_dir / "a.txt"
    text = "hello"
    file_path.write_text(text)

    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
    monkeypatch.setenv("METADATA_DIRECTORY", str(meta_dir))
    monkeypatch.setenv("BY_ID_DIRECTORY", str(by_id))
    monkeypatch.setenv("BY_PATH_DIRECTORY", str(by_path))

    import main as hi

    importlib.reload(hi)

    doc_id = hi.duplicate_finder.compute_hash(file_path)
    doc = {
        "id": doc_id,
        "paths": {"a.txt": file_path.stat().st_mtime},
        "mtime": file_path.stat().st_mtime,
        "size": file_path.stat().st_size,
        "type": "text/plain",
        "next": "",
        "mod.content": text,
    }
    doc_dir = by_id / doc_id
    doc_dir.mkdir()
    (doc_dir / "document.json").write_text(json.dumps(doc))

    md, mhr, ua_docs, ua_hashes, _ = hi.index_metadata()
    files_docs, hashes = hi.index_files(md, mhr, ua_docs, ua_hashes)

    assert files_docs[doc_id]["mod.content"] == text
