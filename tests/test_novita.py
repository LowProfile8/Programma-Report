from core import movimenti
from core.cedole_suggerite import suggerisci


def test_cedole_suggerite_saltano_incassate_e_prima_acquisto():
    s = {"k": {"nome": "BRC", "categoria": "strutturato", "sottocategoria": "Barrier Reverse Convertible", "cedola_annua_pct": 8, "frequenza_cedola": 4,
               "data_emissione": "2026-01-15", "scadenza": "2027-01-15", "valuta": "EUR"}}
    tx = [{"strumento": "k", "data": "2026-02-20", "tipo": "acquisto", "quantita": 10000}, {"strumento": "k", "data": "2026-04-16", "tipo": "cedola", "quantita": None}]
    r = suggerisci(tx, s, "2026-10-16")
    assert [x["data"] for x in r] == ["2026-07-15", "2026-10-15"]
    assert r[0]["importo"] == 200.0 and not r[0]["condizionata"]


def test_movimenti_duplicato_e_riconciliazione():
    t = {"data": "2026-03-10", "tipo": "costo", "importo_cassa": -50.0, "valuta": "CHF", "banca": "PF", "conto": "1"}
    assert movimenti.e_duplicato([t], dict(t))
    assert not movimenti.e_duplicato([t], {**t, "importo_cassa": -51.0})
    saldi = [{"banca": "PF", "conto": "1", "valuta": "CHF", "data": "2026-02-28", "saldo": 1000.0}, {"banca": "PF", "conto": "1", "valuta": "CHF", "data": "2026-03-31", "saldo": 950.0}]
    r = movimenti.riconcilia([t], saldi)
    assert r[0]["esito"] == "punto di partenza" and r[1]["esito"] == "ok"
    r = movimenti.riconcilia([], saldi)
    assert r[1]["esito"] == "errore" and abs(r[1]["differenza"] + 50) < 1e-9


def test_stato_riga():
    assert movimenti.stato_riga({"tipo": "cedola", "importo_cassa": 10, "strumento": ""}) == "da completare"
    assert movimenti.stato_riga({"tipo": "costo", "importo_cassa": -5, "fonte": "strategia"}) == "previsto"
