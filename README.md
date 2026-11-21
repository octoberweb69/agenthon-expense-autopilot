# Agenthon starter

Scheletro per l'AGENTHON (track Agentic AI in azienda): **Google ADK + Gemini → FastAPI → Streamlit**.

```
app/
  config.py          configurazione da .env (modello, percorsi)
  agent/agent.py     definizione agente + istruzioni (root_agent)
  agent/tools.py     tool: lettura dati + azioni (ticket, bozza email, approvazione umana)
  runner.py          esecuzione agente + traccia delle chiamate ai tool
  api.py             FastAPI: /health, /chat, /outbox
ui/streamlit_app.py  chat + pannello delle azioni + "ragionamento" espandibile
data/*.json          dati finti (fatture, clienti, email) → sostituiscili con quelli della sfida
tests/               test dei tool (girano offline)
pitch/PITCH.md       schema del pitch da 3 minuti
```

## Avvio locale

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # poi inserisci GOOGLE_API_KEY
pytest -q                   # 5 test, nessuna chiamata al modello
uvicorn app.api:app --reload            # terminale 1 → http://localhost:8000/docs
streamlit run ui/streamlit_app.py       # terminale 2 → http://localhost:8501
```

Dev UI di ADK (utile per fare debug di eventi e tool): `adk web app` → http://localhost:8000
(se l'API è già attiva, aggiungi `--port 8100`).

## Sabato: dove intervenire

1. **`data/`**: metti i dati della sfida (JSON; `search_records` funziona su qualsiasi lista di oggetti).
2. **`tools.py`**: aggiungi i tool specifici. Funzione con type hints + docstring chiara, ritorna `dict` con `status`, poi aggiungila a `ALL_TOOLS`.
3. **`agent.py`**: adatta `INSTRUCTION` al dominio.
4. **Modello**: cambia `AGENT_MODEL` nel `.env`.

Prompt di prova con i dati finti:
> Controlla le fatture scadute, verifica se ci sono email dei clienti collegate e prepara le azioni necessarie.
