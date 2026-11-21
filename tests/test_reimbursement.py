"""Rimborso bloccato in codice finché non c'è un'approvazione umana valida; tutto finisce nel registro."""
import json

import pytest

from app import expenses
from app.expenses import decide_approval, pay_reimbursement, read_log, request_approval


@pytest.fixture(autouse=True)
def tmp_registro(tmp_path, monkeypatch):
    monkeypatch.setattr(expenses, "REGISTRO", tmp_path / "registro.jsonl")


def tipi():
    return [e["tipo"] for e in read_log()]


def test_nota_regolare_si_paga_senza_approvazione():
    r = pay_reimbursement("NS-101")
    assert r["status"] == "ok"
    assert r["pagamento"]["importo"] == pytest.approx(219.40)
    assert tipi() == ["rimborso_pagato"]


def test_nota_bloccata_non_si_paga_e_il_tentativo_resta_nel_registro():
    r = pay_reimbursement("NS-102")
    assert r["status"] == "rifiutato"
    assert "R2" in r["motivo"]
    assert tipi() == ["pagamento_bloccato"]


def test_nota_sopra_soglia_non_si_paga_senza_approvazione():
    assert pay_reimbursement("NS-106")["status"] == "rifiutato"


def test_richiesta_di_approvazione_resta_in_attesa_e_non_sblocca_il_pagamento():
    r = request_approval("NS-106", "Nota sopra i 500 €")
    assert r["status"] == "in_attesa" and r["approvatore"] == "Paolo Gatti"
    assert pay_reimbursement("NS-106")["status"] == "rifiutato"


def test_approva_solo_l_approvatore_indicato():
    request_approval("NS-106", "Nota sopra i 500 €")
    r = decide_approval("NS-106", "approvata", da="Elena Russo")  # è la dipendente stessa
    assert r["status"] == "error"
    assert pay_reimbursement("NS-106")["status"] == "rifiutato"


def test_dopo_l_approvazione_il_pagamento_passa():
    request_approval("NS-106", "Nota sopra i 500 €")
    assert decide_approval("NS-106", "approvata", da="Paolo Gatti")["status"] == "ok"
    r = pay_reimbursement("NS-106")
    assert r["status"] == "ok" and r["pagamento"]["approvato_da"] == "Paolo Gatti"


def test_approvazione_rifiutata_blocca_il_pagamento():
    request_approval("NS-106", "Nota sopra i 500 €")
    decide_approval("NS-106", "rifiutata", da="Paolo Gatti")
    assert pay_reimbursement("NS-106")["status"] == "rifiutato"


def test_il_responsabile_puo_approvare_un_eccezione():
    request_approval("NS-102", "Hotel sopra limite e cena con vino")
    decide_approval("NS-102", "approvata", da="Marco Bruno", nota="Fiera in città, hotel economici esauriti")
    assert pay_reimbursement("NS-102")["status"] == "ok"


def test_non_si_decide_senza_una_richiesta_in_attesa():
    assert decide_approval("NS-106", "approvata", da="Paolo Gatti")["status"] == "error"


def test_decisione_non_valida():
    request_approval("NS-106", "Nota sopra i 500 €")
    assert decide_approval("NS-106", "forse", da="Paolo Gatti")["status"] == "error"


def test_nessun_doppio_pagamento():
    pay_reimbursement("NS-101")
    r = pay_reimbursement("NS-101")
    assert r["status"] == "rifiutato" and "già" in r["motivo"]
    assert tipi().count("rimborso_pagato") == 1


def test_il_registro_dice_chi_ha_fatto_cosa():
    request_approval("NS-106", "Nota sopra i 500 €")
    decide_approval("NS-106", "approvata", da="Paolo Gatti")
    pay_reimbursement("NS-106")
    log = read_log()
    assert [(e["tipo"], e["attore"]) for e in log] == [
        ("richiesta_approvazione", "agente"),
        ("approvazione_decisa", "Paolo Gatti"),
        ("rimborso_pagato", "agente"),
    ]
    assert all(e["nota_id"] == "NS-106" and e["ts"] for e in log)
    json.dumps(log)  # serializzabile per API e UI


def test_l_agente_non_ha_il_tool_per_approvare():
    from app.agent.tools import ALL_TOOLS
    nomi = {t.__name__ for t in ALL_TOOLS}
    assert {"pay_reimbursement", "request_approval"} <= nomi
    assert "decide_approval" not in nomi
