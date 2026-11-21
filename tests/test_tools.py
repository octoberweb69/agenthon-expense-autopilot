"""Test dei tool senza chiamare il modello (gira anche offline)."""
import pytest

from app import config
from app.agent import tools


@pytest.fixture(autouse=True)
def tmp_outbox(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "OUTBOX", tmp_path / "outbox.jsonl")


def test_list_datasets():
    r = tools.list_datasets()
    assert r["status"] == "ok" and r["datasets"]["fatture"] == 5


def test_search_by_field():
    r = tools.search_records("fatture", "scaduta", field="stato")
    assert r["count"] == 2


def test_search_missing_dataset():
    assert tools.search_records("inesistente")["status"] == "error"


def test_get_record():
    assert tools.get_record("clienti", "C-03")["record"]["referente"] == "Paolo Verdi"


def test_actions_write_outbox():
    tools.create_ticket("Verifica pagamento", "Controllare contabile", "alta")
    tools.draft_email("a@b.it", "Oggetto", "Testo")
    tools.request_human_approval("Rateizzazione", "Richiesta cliente")
    lines = tools.OUTBOX.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
