from __future__ import annotations

# mypy: disable-error-code=misc
import re
import textwrap
import hashlib
from pathlib import Path
import pytest
from collections.abc import Iterable
from pytest import Item

GHERKIN_FENCE_RE = re.compile(
    r"(^|\n)```(?:gherkin|feature)\s*\n(?P<body>.*?)(?:\n)```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_gherkin(md_text: str) -> list[str]:
    return [m.group("body").strip() for m in GHERKIN_FENCE_RE.finditer(md_text)]


class MdFeatureModule(pytest.Module):  # type: ignore[misc]
    """Synthetic module that loads scenarios from generated .feature files."""

    def collect(self) -> Iterable[Item]:
        yield from super().collect()


def pytest_collect_file(
    file_path: Path, parent: pytest.Collector
) -> pytest.Collector | None:
    if file_path.name != "SPEC.md":
        return None
    text = file_path.read_text(encoding="utf-8")
    blocks = _extract_gherkin(text)
    if not blocks:
        return None

    tmpdir = Path(parent.config.cache.makedir("md_features"))
    feature_paths = []
    for i, body in enumerate(blocks, 1):
        body = textwrap.dedent(body)
        h = hashlib.sha1(body.encode("utf-8")).hexdigest()[:12]
        fpath = tmpdir / f"F1_{i:02d}_{h}.feature"
        fpath.write_text(body + "\n", encoding="utf-8")
        feature_paths.append(str(fpath))

    code = "from pytest_bdd import scenarios\n" + "".join(
        f"scenarios({feature_paths[i]!r})\n" for i in range(len(feature_paths))
    )
    py_path = tmpdir / "md_features_F1_autogen.py"
    py_path.write_text(textwrap.dedent(code), encoding="utf-8")

    return MdFeatureModule.from_parent(parent, path=py_path)


# Import step definitions so pytest-bdd can find them
from .tests.acceptance import steps  # noqa: E402,F401
