from pathlib import Path
from pytest_bdd import scenarios

BASE = Path(__file__).resolve().parents[1] / ".pytest_cache" / "md_features"
scenarios(str(BASE))

# pytest-bdd <8 leaves an empty ``usefixtures`` marker on generated scenarios
# which emits PytestWarning. Strip it for cleanliness.
for name, obj in list(globals().items()):
    if name.startswith("test_") and callable(obj):
        marks = getattr(obj, "pytestmark", [])
        obj.pytestmark = [
            m for m in marks if not (m.name == "usefixtures" and not m.args)
        ]
