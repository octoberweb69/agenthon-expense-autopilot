"""UI demo. Avvio: streamlit run ui/streamlit_app.py"""
import os
import uuid

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Agenthon", page_icon="🤖", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:8]
    st.session_state.history = []

chat_col, side_col = st.columns([3, 2])

with side_col:
    st.subheader("⚙️ Azioni dell'agente")
    if st.button("Svuota outbox"):
        httpx.delete(f"{API}/outbox")
    try:
        items = httpx.get(f"{API}/outbox", timeout=5).json()
    except httpx.HTTPError:
        items = []
        st.error(f"Backend non raggiungibile su {API}")
    icons = {"ticket": "🎫", "email_draft": "✉️", "approval_request": "🛑"}
    for it in reversed(items):
        label = it.get("title") or it.get("subject") or it.get("action")
        with st.expander(f"{icons.get(it['type'], '•')} {label}"):
            st.json(it)

with chat_col:
    st.title("🤖 Agente operativo")
    st.caption(f"Sessione {st.session_state.session_id}")

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("models"):
                st.caption("Modello: " + " → ".join(msg["models"]))
            if msg.get("trace"):
                with st.expander(f"🔍 Ragionamento: {len(msg['trace'])} passi"):
                    for step in msg["trace"]:
                        if step["type"] == "call":
                            st.markdown(f"**→ {step['tool']}** `{step['args']}`")
                        else:
                            st.json(step["result"], expanded=False)

    if prompt := st.chat_input("Cosa deve fare l'agente?"):
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.spinner("L'agente sta lavorando…"):
            try:
                r = httpx.post(f"{API}/chat", timeout=120, json={
                    "message": prompt, "session_id": st.session_state.session_id})
                r.raise_for_status()
                data = r.json()
                st.session_state.history.append(
                    {"role": "assistant", "content": data["answer"], "trace": data["trace"],
                     "models": data.get("models", [])})
            except httpx.HTTPError as e:
                detail = getattr(getattr(e, "response", None), "text", str(e))
                st.session_state.history.append({"role": "assistant", "content": f"❌ {detail}"})
        st.rerun()
