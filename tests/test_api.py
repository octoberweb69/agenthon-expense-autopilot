"""API per la UI: panoramica, dettaglio, decisione umana, registro, reset. Nessuna chiamata al modello."""
import pytest
from fastapi.testclient import TestClient

from app import api, expenses
from app.agent import tools


@pytest.fixture(autouse=True)
def tmp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(expenses, "REGISTRO", tmp_path / "registro.jsonl")
    monkeypatch.setattr(tools, "OUTBOX", tmp_path / "outbox.jsonl")


client = TestClient(api.app)


def test_panoramica_note():
    r = client.get("/notes")
    assert r.status_code == 200
    assert {n["nota_id"] for n in r.json()} == {f"NS-10{i}" for i in range(1, 8)}


def test_dettaglio_nota_con_registro():
    expenses.request_approval("NS-106", "Sopra soglia")
    r = client.get("/notes/NS-106").json()
    assert r["esito"] == "richiede_approvazione"
    assert [e["tipo"] for e in r["registro"]] == ["richiesta_approvazione"]


def test_dettaglio_nota_inesistente():
    assert client.get("/notes/NS-999").status_code == 404


def test_decisione_umana_dal_pannello():
    expenses.request_approval("NS-106", "Sopra soglia")
    r = client.post("/approvals/NS-106", json={"decisione": "approvata", "da": "Paolo Gatti"})
    assert r.status_code == 200
    assert expenses.pay_reimbursement("NS-106")["status"] == "ok"


def test_decisione_della_persona_sbagliata_rifiutata():
    expenses.request_approval("NS-106", "Sopra soglia")
    r = client.post("/approvals/NS-106", json={"decisione": "approvata", "da": "Elena Russo"})
    assert r.status_code == 400
    assert "Paolo Gatti" in r.json()["detail"]


def test_registro_completo():
    expenses.pay_reimbursement("NS-101")
    assert [e["tipo"] for e in client.get("/log").json()] == ["rimborso_pagato"]


def test_reset_svuota_registro_e_outbox():
    expenses.pay_reimbursement("NS-101")
    tools.draft_email("a@azienda.example", "Oggetto", "Testo")
    assert client.post("/reset").status_code == 200
    assert client.get("/log").json() == [] and client.get("/outbox").json() == []


def test_health_mostra_i_modelli():
    h = client.get("/health").json()
    assert h["status"] == "ok" and "model" in h and "pay_reimbursement" in h["tools"]
