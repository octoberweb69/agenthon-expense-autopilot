"""Backend FastAPI. Avvio: uvicorn app.api:app --reload"""
import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import expenses
from app.agent import tools
from app.config import AGENT_FALLBACK_MODELS, AGENT_MODEL

app = FastAPI(title="Expense Autopilot")


class ChatIn(BaseModel):
    message: str
    user_id: str = "demo"
    session_id: str = "s1"


class DecisionIn(BaseModel):
    decisione: str  # "approvata" | "rifiutata"
    da: str         # nome della persona che decide
    nota: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "model": AGENT_MODEL, "fallback_models": AGENT_FALLBACK_MODELS,
            "tools": [t.__name__ for t in tools.ALL_TOOLS]}


@app.post("/chat")
async def chat_endpoint(body: ChatIn):
    from app.runner import chat  # import lazy: /health funziona anche senza API key
    try:
        return await chat(body.message, body.user_id, body.session_id)
    except Exception as e:  # in demo meglio un errore leggibile che uno stacktrace
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ---------- NOTE SPESE ----------

@app.get("/notes")
def notes():
    return expenses.list_expense_reports()["note"]


@app.get("/notes/{nota_id}")
def note_detail(nota_id: str):
    r = expenses.check_expense_report(nota_id)
    if r["status"] != "ok":
        raise HTTPException(status_code=404, detail=r["message"])
    return {**r, "registro": expenses.read_log(nota_id)}


@app.post("/approvals/{nota_id}")
def decide(nota_id: str, body: DecisionIn):
    """Decisione UMANA: l'unica strada per approvare (l'agente non ha questo strumento)."""
    r = expenses.decide_approval(nota_id, body.decisione, da=body.da, nota=body.nota)
    if r["status"] != "ok":
        raise HTTPException(status_code=400, detail=r["message"])
    return r


@app.get("/log")
def log():
    return expenses.read_log()


@app.post("/reset")
def reset():
    """Riparte da zero per la demo: svuota registro e outbox (i dati delle note restano)."""
    expenses.REGISTRO.unlink(missing_ok=True)
    tools.OUTBOX.unlink(missing_ok=True)
    return {"status": "ok"}


# ---------- OUTBOX (bozze email) ----------

@app.get("/outbox")
def outbox():
    if not tools.OUTBOX.exists():
        return []
    return [json.loads(l) for l in tools.OUTBOX.read_text(encoding="utf-8").splitlines() if l.strip()]


@app.delete("/outbox")
def clear_outbox():
    tools.OUTBOX.unlink(missing_ok=True)
    return {"status": "ok"}
