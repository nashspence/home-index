from pathlib import Path
from pytest_bdd import scenarios

BASE = Path(__file__).resolve().parents[1] / ".pytest_cache" / "md_features"
scenarios(str(BASE))
