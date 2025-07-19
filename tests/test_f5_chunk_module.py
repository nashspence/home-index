import json


def test_check_returns_true_when_no_content(tmp_path):
    from features.F5.chunk_module import main as chunk_module

    file_path = tmp_path / "file.txt"
    file_path.write_text("hello")
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    assert chunk_module.check(file_path, {}, meta_dir)


def test_check_detects_identical_content(tmp_path):
    from features.F5.chunk_module import main as chunk_module

    file_path = tmp_path / "file.txt"
    file_path.write_text("hello")
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    (meta_dir / "content.json").write_text(json.dumps("hello"))
    assert not chunk_module.check(file_path, {}, meta_dir)


def test_run_reads_file_and_returns_document(tmp_path):
    from features.F5.chunk_module import main as chunk_module

    file_path = tmp_path / "file.txt"
    file_path.write_text("hello")
    doc = {"id": "1"}
    result = chunk_module.run(file_path, doc, tmp_path)
    assert result["document"] == doc
    assert result["content"] == "hello"
