"""UI demo. Avvio: streamlit run ui/streamlit_app.py  (porta in .streamlit/config.toml)"""
import os
import uuid

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Expense Autopilot", page_icon="🧾", layout="wide")

# Layout a tutto schermo senza scorrimento della pagina: chat e pannello scorrono al loro interno
st.markdown("""
<style>
  .block-container { padding-top: 3rem; padding-bottom: 0.5rem; }
  [data-testid="stMain"] { overflow: hidden; }
  .st-key-chat_box { height: calc(100vh - 340px) !important; min-height: 200px; }
  .st-key-pannello { height: calc(100vh - 3.5rem); overflow-y: auto; overflow-x: hidden; padding-right: 0.4rem; }
</style>
""", unsafe_allow_html=True)

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
        if n["esito"] == "pronta_al_rimborso":
            return f"🟢 Regolare, attende {n['approvatore']}"
        return f"🛑 In attesa di {n['approvatore']}"
    return {"pronta_al_rimborso": "🟢 Regolare, da approvare",
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
with side_col.container(key="pannello"):
    if st.session_state.flash:
        kind, text = st.session_state.flash
        getattr(st, kind)(text)
        st.session_state.flash = None

    note = get("/notes", [])
    attesa = [n for n in note if n["approvazione"] == "in_attesa"]
    bozze = get("/outbox", [])
    registro = get("/log", [])

    # Quanto risparmia: si mostra dopo che l'agente ha processato le note
    if any(e["tipo"] == "richiesta_approvazione" for e in registro):
        s = get("/summary", {})
        if s:
            ore, minuti = divmod(s["minuti_risparmiati"], 60)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Righe controllate", s["righe_controllate"], help=f"{s['note']} note spese")
            m2.metric("Anomalie trovate", s["anomalie"])
            m3.metric("Tempo risparmiato", f"~{ore} h {minuti} min",
                      help=f"Stima: {s['minuti_per_riga_stima']} minuti di controllo manuale per riga")
            m4.metric("€ fermati", f"{s['euro_bloccati']:.0f} €",
                      help="Non rimborsabili (alcolici, multe, doppioni, fuori termine) "
                           "+ eccedenze sui limiti di pasti e hotel")

    # Selettore con memoria (le st.tabs tornano alla prima scheda a ogni rerun, es. dopo un'approvazione)
    etichette = {"note": "📋 Note spese", "appr": f"🛑 Approvazioni ({len(attesa)})",
                 "bozze": f"✉️ Bozze ({len(bozze)})", "log": f"📜 Registro ({len(registro)})"}
    sezione = st.segmented_control("Sezione", list(etichette), format_func=etichette.get,
                                   default="note", key="sezione", label_visibility="collapsed") or "note"

    if sezione == "note":
        scelta = None
        if note:
            # Clic su una riga = dettaglio della nota subito sotto
            ev = st.dataframe(
                [{"Nota": n["nota_id"], "Stato": stato_nota(n), "Dipendente": n["dipendente"],
                  "Totale €": n["totale"]} for n in note],
                hide_index=True, width="stretch", height=(len(note) + 1) * 35 + 3,
                on_select="rerun", selection_mode="single-row", key="tabella_note",
                column_config={
                    "Nota": st.column_config.TextColumn(width="small"),
                    "Stato": st.column_config.TextColumn(width="medium"),
                    "Dipendente": st.column_config.TextColumn(width="medium"),
                    "Totale €": st.column_config.NumberColumn(format="%.2f", width="small")})
            righe = ev.selection.rows if ev and ev.selection else []
            scelta = note[righe[0]]["nota_id"] if righe else None
            if not scelta:
                st.caption("👆 Clicca una nota per vedere i controlli spesa per spesa.")
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

    if sezione == "appr":
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
                if n["esito"] == "pronta_al_rimborso":
                    st.success("Regolare: tutti i controlli superati, nessuna anomalia.", icon="🟢")
                st.caption(f"Motivo dell'agente: {richiesta.get('motivo', '-')}")
                for s in d.get("spese", []):
                    for v in s["violazioni"]:
                        st.markdown(f"- {s['id']} **{v['regola']}** {v['motivo']}")
                c1, c2 = st.columns([2, 3])
                chi = c1.selectbox("Decido come", persone, key=f"chi_{n['nota_id']}",
                                   index=persone.index(n["approvatore"]) if n["approvatore"] in persone else 0)
                motivazione = c2.text_input("Nota (facoltativa)", key=f"nota_{n['nota_id']}")
                errore = st.session_state.get(f"err_{n['nota_id']}")
                if errore:
                    st.error(f"⛔ Rifiutato dal sistema: {errore}")
                b1, b2 = st.columns(2)
                for col, decisione, label in ((b1, "approvata", "✅ Approva"), (b2, "rifiutata", "⛔ Rifiuta")):
                    if col.button(label, key=f"{decisione}_{n['nota_id']}", width="stretch"):
                        r = httpx.post(f"{API}/approvals/{n['nota_id']}", timeout=10,
                                       json={"decisione": decisione, "da": chi, "nota": motivazione})
                        if r.status_code == 200:
                            st.session_state.pop(f"err_{n['nota_id']}", None)
                            st.session_state.flash = ("success", f"{n['nota_id']} {decisione} da {chi}")
                            st.toast(f"✅ {n['nota_id']} {decisione} da {chi}")
                        else:
                            st.session_state[f"err_{n['nota_id']}"] = r.json().get("detail")
                            st.toast(f"⛔ {r.json().get('detail')}")
                        st.rerun()

    if sezione == "bozze":
        if not bozze:
            st.caption("Nessuna bozza.")
        for b in reversed(bozze):
            with st.expander(f"✉️ {b.get('to')} · {b.get('subject')}"):
                st.text(b.get("body", ""))
                st.caption("Bozza: non inviata.")

    if sezione == "log":
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

    # Chat in un riquadro ad altezza fissa: la pagina non si allunga e il pannello note resta visibile
    chat_box = st.container(height=520, border=True, autoscroll=True, key="chat_box")  # altezza reale dal CSS
    if not st.session_state.history:
        chat_box.caption("Premi ▶ Processa o scrivi una richiesta qui sotto.")
    for msg in st.session_state.history:
        with chat_box.chat_message(msg["role"]):
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
