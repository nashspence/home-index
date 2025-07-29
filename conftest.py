from pathlib import Path
from features.conftest import *  # noqa: F401,F403

pytest_plugins: list[str] = []

_ROOT = Path(__file__).parent
_FEATURES = _ROOT / "features"


def _add_if_exists(path: Path) -> None:
    if path.is_file():
        mod = ".".join(path.relative_to(_ROOT).with_suffix("").parts)
        pytest_plugins.append(mod)


if _FEATURES.exists():
    for fx in _FEATURES.iterdir():
        if not fx.is_dir():
            continue
        base = fx / "tests" / "acceptance"
        _add_if_exists(base / "steps.py")
        _add_if_exists(base / "conftest.py")
