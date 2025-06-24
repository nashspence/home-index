import importlib


def test_migrate_doc_adds_paths_list():
    import home_index.main as hi

    importlib.reload(hi)

    doc = {"id": "1", "paths": {"a.txt": 1.0}}
    assert hi.migrate_doc(doc)
    assert doc["paths_list"] == ["a.txt"]
    assert doc["version"] == hi.CURRENT_VERSION

    doc2 = {
        "id": "2",
        "paths": {"b.txt": 1.0},
        "paths_list": ["b.txt"],
        "version": hi.CURRENT_VERSION,
    }
    assert not hi.migrate_doc(doc2)
