import importlib


def test_migrate_doc_adds_paths_list():
    from features.F2 import migrations

    importlib.reload(migrations)

    doc = {"id": "1", "paths": {"a.txt": 1.0}}
    assert migrations.migrate_doc(doc)
    assert doc["paths_list"] == ["a.txt"]
    assert doc["version"] == migrations.CURRENT_VERSION

    doc2 = {
        "id": "2",
        "paths": {"b.txt": 1.0},
        "paths_list": ["b.txt"],
        "version": migrations.CURRENT_VERSION,
    }
    assert not migrations.migrate_doc(doc2)
