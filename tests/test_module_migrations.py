import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
from home_index_module.run_server import apply_migrations_if_needed, load_version


def test_apply_migrations_if_needed(tmp_path):
    meta_dir = tmp_path / "meta"

    calls = []

    def mig1(*args):
        calls.append(1)
        return None, []

    def mig2(*args):
        calls.append(2)
        return None, []

    segs, docs, ver = apply_migrations_if_needed(meta_dir, [mig1, mig2], target_version=2)
    assert ver == 2
    assert calls == [1, 2]
    assert load_version(meta_dir)["version"] == 2

    calls.clear()
    apply_migrations_if_needed(meta_dir, [mig1, mig2], target_version=2)
    assert calls == []
