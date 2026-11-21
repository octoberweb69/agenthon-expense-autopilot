"""Tool dell'agente.

Regole ADK:
- ogni tool è una normale funzione Python con type hints e docstring
  (il modello legge la docstring per capire QUANDO usarla: scrivila bene);
- restituisci sempre un dict con una chiave "status".

Sabato: tieni i tool generici qui sotto e aggiungi quelli specifici della sfida.
"""
import json
import uuid
from datetime import datetime

from app.config import DATA_DIR, OUTBOX


def _load(name: str) -> list[dict]:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _append_outbox(record: dict) -> dict:
    record = {"id": uuid.uuid4().hex[:8], "created_at": datetime.now().isoformat(timespec="seconds"), **record}
    OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    with OUTBOX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


# ---------- LETTURA ----------

def list_datasets() -> dict:
    """Elenca i dataset disponibili (es. fatture, email, clienti) con il numero di record."""
    datasets = {p.stem: len(_load(p.stem)) for p in sorted(DATA_DIR.glob("*.json"))}
    return {"status": "ok", "datasets": datasets}


def search_records(dataset: str, query: str = "", field: str = "") -> dict:
    """Cerca record in un dataset.

    Args:
        dataset: nome del dataset (vedi list_datasets), es. "fatture".
        query: testo da cercare (case-insensitive). Vuoto = tutti i record.
        field: se indicato, cerca solo in quel campo (es. "cliente", "stato").
    """
    rows = _load(dataset)
    if not rows:
        return {"status": "error", "message": f"Dataset '{dataset}' inesistente o vuoto."}
    q = query.lower().strip()

    def match(r: dict) -> bool:
        if not q:
            return True
        haystack = str(r.get(field, "")) if field else json.dumps(r, ensure_ascii=False)
        return q in haystack.lower()

    found = [r for r in rows if match(r)]
    return {"status": "ok", "count": len(found), "records": found[:20]}


def get_record(dataset: str, record_id: str) -> dict:
    """Restituisce un singolo record di un dataset dato il suo campo "id"."""
    for r in _load(dataset):
        if str(r.get("id")) == record_id:
            return {"status": "ok", "record": r}
    return {"status": "error", "message": f"Record {record_id} non trovato in {dataset}."}


def totale_fatture(stato: str) -> dict:
    """Calcola numero e importo totale delle fatture con un certo stato.
    Usala quando serve sapere quanto devono pagare i clienti (es. totale scaduto).

    Args:
        stato: "scaduta", "aperta" o "pagata".
    """
    # 1. carica le fatture
    fatture = _load("fatture")
    # 2. tieni solo quelle con lo stato richiesto
    scelte = [f for f in fatture if f["stato"] == stato]
    # 3. restituisci status, numero e totale
    return {"status": "ok", "numero": len(scelte), "totale": round(sum(f["importo"] for f in scelte), 2)}




# ---------- AZIONI (scrivono nell'outbox, visibile nella UI) ----------

def create_ticket(title: str, description: str, priority: str = "media", assignee: str = "") -> dict:
    """Apre un ticket/attività da far gestire a una persona.

    Args:
        title: titolo breve.
        description: cosa va fatto e perché.
        priority: "bassa", "media" o "alta".
        assignee: persona o ufficio a cui assegnarlo (opzionale).
    """
    rec = _append_outbox({"type": "ticket", "title": title, "description": description,
                          "priority": priority, "assignee": assignee})
    return {"status": "ok", "ticket": rec}


def draft_email(to: str, subject: str, body: str) -> dict:
    """Prepara una BOZZA di email (non la invia). Usala quando serve comunicare con qualcuno."""
    rec = _append_outbox({"type": "email_draft", "to": to, "subject": subject, "body": body})
    return {"status": "ok", "draft": rec}


def request_human_approval(action: str, reason: str) -> dict:
    """Chiede l'approvazione di un umano prima di un'azione rischiosa o irreversibile
    (pagamenti, invii esterni, cancellazioni). Non eseguire l'azione: registra la richiesta."""
    rec = _append_outbox({"type": "approval_request", "action": action, "reason": reason, "state": "pending"})
    return {"status": "pending", "approval": rec}


ALL_TOOLS = [list_datasets, search_records, get_record, create_ticket, draft_email, request_human_approval]
