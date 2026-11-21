"""Test dei tool generici senza chiamare il modello (gira anche offline)."""
import pytest

from app.agent import tools


@pytest.fixture(autouse=True)
def tmp_outbox(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "OUTBOX", tmp_path / "outbox.jsonl")


def test_list_datasets_solo_note_spese():
    r = tools.list_datasets()
    assert r["status"] == "ok"
    assert set(r["datasets"]) == {"dipendenti", "note_spese", "policy", "spese"}
    assert r["datasets"]["note_spese"] == 7


def test_search_by_field():
    r = tools.search_records("spese", "hotel", field="categoria")
    assert r["count"] == 4


def test_search_missing_dataset():
    assert tools.search_records("inesistente")["status"] == "error"


def test_get_record():
    assert tools.get_record("dipendenti", "D-03")["record"]["nome"] == "Sara Galli"


def test_draft_email_scrive_solo_una_bozza_nell_outbox():
    r = tools.draft_email("sara.galli@azienda.example", "Taxi del 13/11", "Ci serve la motivazione.")
    assert r["status"] == "ok"
    lines = tools.OUTBOX.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and '"email_draft"' in lines[0]


def test_strumenti_dell_agente():
    nomi = {t.__name__ for t in tools.ALL_TOOLS}
    assert nomi == {"list_datasets", "search_records", "get_record", "list_expense_reports",
                    "check_expense_report", "request_approval", "pay_reimbursement", "read_log",
                    "draft_email"}
