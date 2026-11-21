import sys
from pathlib import Path

# `adk web app` importa questo pacchetto come modulo "agent":
# aggiungo la root del progetto al path così funzionano gli import `app.*`.
_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from . import agent  # noqa: E402,F401  (richiesto da `adk web`)
