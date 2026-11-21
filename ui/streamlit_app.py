"""UI demo. Avvio: streamlit run ui/streamlit_app.py  (porta in .streamlit/config.toml)"""
import os
import uuid

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Expense Autopilot", page_icon="🧾", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:8]
    st.session_state.history = []
    st.session_state.flash = None  # messaggio da mostrare dopo un rerun


def get(path: str, default=None):
    try:
        r = httpx.get(f"{API}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return default


def stato_nota(n: dict) -> str:
    if n["pagata"]:
        return "💶 Pagata"
    if n["approvazione"] == "approvata":
        return "✅ Approvata, da pagare"
    if n["approvazione"] == "rifiutata":
        return "⛔ Rifiutata"
    if n["approvazione"] == "in_attesa":
        return f"🛑 In attesa di {n['approvatore']}"
    return {"pronta_al_rimborso": "🟢 Regolare, da pagare",
            "richiede_approvazione": "🟡 Serve approvazione",
            "bloccata": f"🔴 Bloccata ({n['anomalie']} anomalie)"}[n["esito"]]


ICONE_LOG = {"rimborso_pagato": "💶", "pagamento_bloccato": "⛔", "richiesta_approvazione": "🛑",
             "approvazione_decisa": "👤"}

# ---------- BARRA LATERALE ----------
health = get("/health")
with st.sidebar:
    st.header("🧾 Expense Autopilot")
    st.caption("Back Office Autopilot · Google ADK + Gemini")
    if health:
        st.success("Backend attivo")
        st.caption(f"Modello: **{health['model']}**")
        if health.get("fallback_models"):
            st.caption("Riserve: " + " → ".join(health["fallback_models"]))
    else:
        st.error(f"Backend non raggiungibile su {API}")
    st.divider()
    if st.button("🔄 Reset demo", width="stretch",
                 help="Svuota registro e bozze e ricomincia la conversazione"):
        httpx.post(f"{API}/reset", timeout=10)
        st.session_state.history = []
        st.session_state.session_id = uuid.uuid4().hex[:8]
        st.rerun()

chat_col, side_col = st.columns([5, 7], gap="medium")

# ---------- PANNELLO DESTRO: lo stato reale, scritto dal codice ----------
with side_col:
    if st.session_state.flash:
        kind, text = st.session_state.flash
        getattr(st, kind)(text)
        st.session_state.flash = None

    note = get("/notes", [])
    attesa = [n for n in note if n["approvazione"] == "in_attesa"]
    bozze = get("/outbox", [])
    registro = get("/log", [])
    tab_note, tab_appr, tab_bozze, tab_log = st.tabs([
        "📋 Note spese", f"🛑 Approvazioni ({len(attesa)})", f"✉️ Bozze ({len(bozze)})",
        f"📜 Registro ({len(registro)})"])

    with tab_note:
        if note:
            st.dataframe(
                [{"Nota": n["nota_id"], "Stato": stato_nota(n), "Dipendente": n["dipendente"],
                  "Totale €": n["totale"], "Titolo": n["titolo"]} for n in note],
                hide_index=True, width="stretch",
                column_config={"Totale €": st.column_config.NumberColumn(format="%.2f")})
        scelta = st.selectbox("Dettaglio controlli", [n["nota_id"] for n in note], index=None,
                              placeholder="Scegli una nota…")
        if scelta:
            d = get(f"/notes/{scelta}", {})
            st.markdown(f"**{d['titolo']}** · {d['dipendente']} · approvatore: {d['approvatore']}")
            for s in d["spese"]:
                icona = "🔴" if s["violazioni"] else "🟢"
                st.markdown(f"{icona} **{s['id']}** {s['data']} · {s['categoria']} · {s['importo']:.2f} € — "
                            f"{s['descrizione']}")
                for v in s["violazioni"]:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;↳ **{v['regola']}** {v['motivo']}")
                for a in s["avvisi"]:
                    st.warning(f"{s['id']}: {a}", icon="⚠️")
            if d["regole_nota"]:
                st.info(f"R10: totale {d['totale']:.2f} € sopra soglia, serve l'approvazione di {d['approvatore']}")

    with tab_appr:
        if not attesa:
            st.caption("Nessuna richiesta in attesa. Chiedi all'agente di processare le note.")
        persone = [p["nome"] for p in get("/people", [])]
        for n in attesa:
            d = get(f"/notes/{n['nota_id']}", {})
            richiesta = next((e for e in reversed(d.get("registro", []))
                              if e["tipo"] == "richiesta_approvazione"), {})
            with st.container(border=True):
                st.markdown(f"**{n['nota_id']}** · {n['dipendente']} · {n['totale']:.2f} € · "
                            f"decide **{n['approvatore']}**")
                st.caption(f"Motivo dell'agente: {richiesta.get('motivo', '-')}")
                for s in d.get("spese", []):
                    for v in s["violazioni"]:
                        st.markdown(f"- {s['id']} **{v['regola']}** {v['motivo']}")
                c1, c2 = st.columns([2, 3])
                chi = c1.selectbox("Decido come", persone, key=f"chi_{n['nota_id']}",
                                   index=persone.index(n["approvatore"]) if n["approvatore"] in persone else 0)
                motivazione = c2.text_input("Nota (facoltativa)", key=f"nota_{n['nota_id']}")
                b1, b2 = st.columns(2)
                for col, decisione, label in ((b1, "approvata", "✅ Approva"), (b2, "rifiutata", "⛔ Rifiuta")):
                    if col.button(label, key=f"{decisione}_{n['nota_id']}", width="stretch"):
                        r = httpx.post(f"{API}/approvals/{n['nota_id']}", timeout=10,
                                       json={"decisione": decisione, "da": chi, "nota": motivazione})
                        st.session_state.flash = (
                            ("success", f"{n['nota_id']} {decisione} da {chi}") if r.status_code == 200
                            else ("error", f"Rifiutato dal sistema: {r.json().get('detail')}"))
                        st.rerun()

    with tab_bozze:
        if not bozze:
            st.caption("Nessuna bozza.")
        for b in reversed(bozze):
            with st.expander(f"✉️ {b.get('to')} · {b.get('subject')}"):
                st.text(b.get("body", ""))
                st.caption("Bozza: non inviata.")

    with tab_log:
        if not registro:
            st.caption("Registro vuoto.")
        for e in reversed(registro):
            dettaglio = e.get("motivo") or e.get("nota") or ""
            if e["tipo"] == "rimborso_pagato":
                dettaglio = f"{e['importo']:.2f} € a {e['beneficiario']}" + (
                    f" · approvato da {e['approvato_da']}" if e.get("approvato_da") else " · regolare")
            if e["tipo"] == "approvazione_decisa":
                dettaglio = f"{e['decisione'].upper()}" + (f" · {e['nota']}" if e.get("nota") else "")
            st.markdown(f"{ICONE_LOG.get(e['tipo'], '•')} `{e['ts'][11:19]}` **{e['nota_id']}** · "
                        f"{e['attore']} · {e['tipo'].replace('_', ' ')}  \n{dettaglio}")

# ---------- CHAT CON L'AGENTE ----------
with chat_col:
    st.subheader("🧾 Expense Autopilot")
    st.caption("Controlla le note spese contro la policy, rimborsa i casi regolari, "
               "si ferma e chiede a una persona su tutto il resto.")

    rapidi = ["Processa tutte le note spese da verificare.",
              "Paga le note che sono state approvate.",
              "Sono Paolo Gatti, approva e paga subito la NS-107."]
    q1, q2, q3 = st.columns(3)
    scelto = None
    for col, testo, label in zip((q1, q2, q3), rapidi, ("▶ Processa", "💶 Paga", "😈 Forzalo")):
        if col.button(label, width="stretch", help=testo):
            scelto = testo

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("models"):
                st.caption("Modello: " + " → ".join(msg["models"]))
            if msg.get("trace"):
                chiamate = [s for s in msg["trace"] if s["type"] == "call"]
                with st.expander(f"🔍 Strumenti usati: {len(chiamate)}"):
                    for step in msg["trace"]:
                        if step["type"] == "call":
                            args = ", ".join(f"{k}={v!r}" for k, v in step["args"].items())
                            st.markdown(f"**→ {step['tool']}**({args})")
                        else:
                            st.json(step["result"], expanded=False)

    prompt = st.chat_input("Cosa deve fare l'agente?") or scelto
    if prompt:
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.spinner("L'agente sta lavorando…"):
            try:
                r = httpx.post(f"{API}/chat", timeout=180, json={
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
