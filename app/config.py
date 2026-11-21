"""Configurazione centralizzata: tutto da variabili d'ambiente / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

APP_NAME = "agenthon"
AGENT_MODEL = os.getenv("AGENT_MODEL", "gemini-3.8-flash")
# Modelli di riserva, in ordine, separati da virgola: usati se il principale dà 429/5xx.
AGENT_FALLBACK_MODELS = [m.strip() for m in os.getenv("AGENT_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(",") if m.strip()]
# Tentativi per ciascun modello (backoff esponenziale) prima di passare al successivo.
AGENT_RETRY_ATTEMPTS = int(os.getenv("AGENT_RETRY_ATTEMPTS", "1"))
# Secondi massimi per singola richiesta al modello: oltre, si passa alla riserva.
# Il timeout viene inoltrato anche a Google come scadenza lato server: sotto i 10 s risponde 400.
AGENT_TIMEOUT_S = max(10, int(os.getenv("AGENT_TIMEOUT_S", "15")))
# Dopo un fallimento il principale viene saltato per questi secondi (le chiamate vanno subito alla riserva).
AGENT_PRIMARY_COOLDOWN_S = int(os.getenv("AGENT_PRIMARY_COOLDOWN_S", "300"))
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
OUTBOX = DATA_DIR / "outbox.jsonl"  # dove finiscono le "azioni" dell'agente
