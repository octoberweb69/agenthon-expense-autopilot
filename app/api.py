"""Backend FastAPI. Avvio: uvicorn app.api:app --reload"""
import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import AGENT_FALLBACK_MODELS, AGENT_MODEL, OUTBOX
from app.agent.tools import ALL_TOOLS

app = FastAPI(title="Agenthon starter")


class ChatIn(BaseModel):
    message: str
    user_id: str = "demo"
    session_id: str = "s1"


@app.get("/health")
def health():
    return {"status": "ok", "model": AGENT_MODEL, "fallback_models": AGENT_FALLBACK_MODELS,
            "tools": [t.__name__ for t in ALL_TOOLS]}


@app.post("/chat")
async def chat_endpoint(body: ChatIn):
    from app.runner import chat  # import lazy: /health funziona anche senza API key
    try:
        return await chat(body.message, body.user_id, body.session_id)
    except Exception as e:  # in demo meglio un errore leggibile che uno stacktrace
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/outbox")
def outbox():
    if not OUTBOX.exists():
        return []
    return [json.loads(l) for l in OUTBOX.read_text(encoding="utf-8").splitlines() if l.strip()]


@app.delete("/outbox")
def clear_outbox():
    OUTBOX.unlink(missing_ok=True)
    return {"status": "ok"}
