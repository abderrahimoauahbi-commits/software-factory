"""Aide commune aux tests du Bootstrap : chemins d'import (lancé avec « python -P »)."""
import sys
from pathlib import Path

BOOTSTRAP = Path(__file__).resolve().parents[1]
FACTORY = BOOTSTRAP.parent
CORE = FACTORY / "core"
for _p in (CORE, BOOTSTRAP):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
