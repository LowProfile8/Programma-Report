"""Flusso completo nell'interfaccia: cliente → strategia (prodotti, incassi) → portafoglio in diretta → report → home (mercato simulato, archivio temporaneo)."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from streamlit.testing.v1 import AppTest

from core import dati, db
import core.calcolo as cc
from core.mercato import Mercato

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _at(vista, **st_):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["_autenticato"] = True
    at.session_state["vista"] = vista
    for k, v in st_.items():
        at.session_state[k] = v
    return at


def _bt(at, testo):
    b = [b for b in at.button if testo in b.label]
    assert b, (testo, [x.label for x in at.button])
    return b[0]


def _ok(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not [e for e in at.error if "Da inserire" not in e.value], [e.value for e in at.error]


class Finta:
    nome = "sim"
    def chiusura(self, t, d): return (d, {"VHYL.L": 66.0, "^GSPC": 5400.0}.get(t, 66.0))
    def cambio(self, da, a, d): return (d, {("EUR", "CHF"): 0.93, ("USD", "CHF"): 0.80, ("CHF", "EUR"): 1 / 0.93, ("CHF", "USD"): 1.25}.get((da, a), 1.0))


def test_flusso_completo():
    db._archivio = db.ArchivioLocale(Path(tempfile.mkdtemp()))
    cc.mercato_reale = lambda manuali=None, snapshot=None: Mercato(Finta())

    # 1 cliente
    at = _at("clienti"); at.run()
    at.text_input(key="nc_nome").set_value("Mario"); at.text_input(key="nc_cogn").set_value("Rossi")
    _bt(at, "Crea cliente").click().run(); _ok(at)
    cid = at.session_state["cli_id"]
    assert dati.carica_cliente(cid)["nome"] == "Mario Rossi"

    # 2 due strategie con valute diverse
    at = _at("cliente", cli_id=cid); at.run()
    at.selectbox(key="npf_val").set_value("EUR")
    _bt(at, "Crea").click().run(); _ok(at)
    at = _at("cliente", cli_id=cid); at.run()
    at.selectbox(key="npf_val").set_value("USD")
    _bt(at, "Crea").click().run(); _ok(at)
    pfs = dati.carica_cliente(cid)["portafogli"]
    assert [p["valuta"] for p in pfs] == ["EUR", "USD"]
    pf = pfs[0]; pid = pf["id"]
    pre = f"np_{pid}"

    def aggiungi(tipo, sub, nome, valuta, extra=None, inv=None, qta=None, prezzo=None, data=None):
        a = _at("cliente", cli_id=cid, cli_pf=pid); a.run()
        a.radio(key=f"{pre}_tipo").set_value(tipo).run()
        opz = a.selectbox(key=f"{pre}_sub_{tipo}").options          # i menu dipendono dal tipo
        assert sub in opz and (tipo != "Obbligazione" or "Barrier Reverse Convertible" not in opz)
        a.selectbox(key=f"{pre}_sub_{tipo}").set_value(sub)
        a.text_input(key=f"{pre}_nome").set_value(nome)
        a.selectbox(key=f"{pre}_val").set_value(valuta)
        for k, (w, v) in (extra or {}).items():
            getattr(a, w)(key=f"{pre}_{k}").set_value(v)
        cat = {"Prodotto strutturato": "strutturato", "ETF": "etf_azioni"}[tipo]
        pct = cat == "strutturato"
        k_ = f"{pre}_{cat}_{int(pct)}"
        if prezzo is not None:
            a.number_input(key=f"{k_}_p").set_value(prezzo)
        if inv is not None:
            a.number_input(key=f"{k_}_inv").set_value(inv)
        if qta is not None:
            a.radio(key=f"{pre}_modo_{cat}").set_value("Quantità / nominale").run()
            a.number_input(key=f"{k_}_q").set_value(qta)
        if data:
            a.date_input(key=f"{pre}_data").set_value(data)
        _bt(a, "Aggiungi il prodotto").click().run()
        assert not a.exception, [e.value for e in a.exception]

    from datetime import date
    aggiungi("Prodotto strutturato", "Barrier Reverse Convertible", "6.93% BRC Multi", "EUR", {"ced": ("number_input", 6.93), "bar": ("number_input", 60.0), "fr": ("selectbox", 4)},
             inv=20000.0, prezzo=100.0, data=date(2026, 1, 6))
    aggiungi("ETF", "ETF azionario", "Vanguard High Div", "USD", {"t1": ("text_input", "VHYL.L"), "set": ("multiselect", ["Finanziario", "Tecnologia"]), "are": ("multiselect", ["Stati Uniti"])},
             qta=100, prezzo=55.0, data=date(2026, 2, 3))
    c = dati.carica_cliente(cid); reg = dati.carica_registro()
    acq = [t for t in c["transazioni"] if t["tipo"] == "acquisto"]
    assert [round(t["importo_cassa"], 2) for t in acq] == [-20000.0, -5500.0] and acq[0]["quantita"] == 20000.0 and acq[0]["prezzo_in_percento"]
    brc = next(s for s in reg.strumenti.values() if s["categoria"] == "strutturato")
    etf = next(s for s in reg.strumenti.values() if s["categoria"] == "etf_azioni")
    assert brc["valutazione"] == "nominale" and brc["prezzo_in_percento"] and not etf["prezzo_in_percento"]
    assert etf["settori"] == {"Finanziario": 0.5, "Tecnologia": 0.5} and etf["aree"] == {"Stati Uniti": 1.0}
    kb = next(k for k, s in reg.strumenti.items() if s["categoria"] == "strutturato")

    # 3 incasso di una cedola dall'interfaccia
    a = _at("cliente", cli_id=cid, cli_pf=pid); a.run()
    a.number_input(key=f"inc_i_{pid}").set_value(173.25)
    a.date_input(key=f"inc_d_{pid}").set_value(date(2026, 4, 6))
    _bt(a, "Registra l'incasso").click().run(); assert not a.exception
    assert any(t["tipo"] == "cedola" and t["importo_cassa"] == 173.25 for t in dati.carica_cliente(cid)["transazioni"])

    # 4 il portafoglio è già «in diretta»: valore, performance, cedole
    a = _at("cliente", cli_id=cid, cli_pf=pid); a.run(); _ok(a)
    L = dati.carica_cliente(cid)["portafogli"][0]["live"]
    assert L["errore"] is None and L["valore"] > 0 and L["proventi"] == pytest.approx(173.25) and L["perf"] is not None
    assert any("Performance dall'inizio" in m.label for m in a.metric)

    # 5 report dentro la strategia
    _bt(a, "Crea il report").click().run(); _ok(a)
    _bt(a, "Calcola").click().run(); assert not a.exception
    if not a.error:
        g = [b for b in a.button if "Genera PDF" in b.label][0]
        if not g.proto.disabled:
            g.click().run(); _ok(a)
            assert a.session_state[f"rep_pdf_{pid}"][0][:4] == b"%PDF"

    # 6 home con gli aggregati e le altre viste
    h = _at("home"); h.run(); _ok(h)
    assert any(m.label == "Clienti" for m in h.metric)
    for v in ("clienti", "report", "archivio_report", "strumenti"):
        x = _at(v, cli_id=cid); x.run(); assert not x.exception, v

    # 7 elimina cliente (accanto a «Salva», con conferma)
    a = _at("cliente", cli_id=cid, cli_pf=pid); a.run()
    _bt(a, "Elimina cliente").click().run()
    _bt(a, "Sì, elimina").click().run()
    assert dati.carica_cliente(cid) is None
