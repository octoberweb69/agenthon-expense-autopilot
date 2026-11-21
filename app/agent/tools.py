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
from app.expenses import (check_expense_report, list_expense_reports, pay_reimbursement, read_log,
                          request_approval)


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
    """Elenca i dataset disponibili (note_spese, spese, dipendenti, policy) con il numero di record."""
    datasets = {p.stem: len(_load(p.stem)) for p in sorted(DATA_DIR.glob("*.json"))}
    return {"status": "ok", "datasets": datasets}


def search_records(dataset: str, query: str = "", field: str = "") -> dict:
    """Cerca record in un dataset.

    Args:
        dataset: nome del dataset (vedi list_datasets), es. "spese".
        query: testo da cercare (case-insensitive). Vuoto = tutti i record.
        field: se indicato, cerca solo in quel campo (es. "categoria", "nota_id").
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


# ---------- AZIONI (scrivono nell'outbox, visibile nella UI) ----------

def draft_email(to: str, subject: str, body: str) -> dict:
    """Prepara una BOZZA di email (non la invia). Usala per chiedere a un dipendente
    ciò che manca (ricevuta, motivazione) o per informarlo dell'esito. Non promettere
    rimborsi che non sono ancora stati pagati.

    Args:
        to: indirizzo email del destinatario (campo "email" nel dataset dipendenti).
        subject: oggetto breve.
        body: testo della bozza.
    """
    # Una sola bozza aperta per destinatario: se l'agente riprocessa le note non duplica le email.
    if OUTBOX.exists():
        for line in OUTBOX.read_text(encoding="utf-8").splitlines():
            old = json.loads(line) if line.strip() else {}
            if old.get("type") == "email_draft" and old.get("to", "").lower() == to.lower():
                return {"status": "gia_presente", "draft": old,
                        "message": f"Esiste già una bozza per {to}: non ne creo un'altra."}
    rec = _append_outbox({"type": "email_draft", "to": to, "subject": subject, "body": body})
    return {"status": "ok", "draft": rec}


# decide_approval NON è qui di proposito: decidere spetta solo a una persona (UI/API).
ALL_TOOLS = [list_datasets, search_records, get_record,
             list_expense_reports, check_expense_report, request_approval, pay_reimbursement, read_log,
             draft_email]
