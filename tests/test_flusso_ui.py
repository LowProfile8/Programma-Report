"""Flusso completo nell'interfaccia: cliente → strategia → portafoglio → andamento → report (mercato simulato, archivio temporaneo)."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from streamlit.testing.v1 import AppTest

from core import dati, db, strategia as stg
import core.calcolo as cc
from core.mercato import Mercato

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _at(vista, **st_):
    at = AppTest.from_file(APP, default_timeout=90)
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
    assert not at.error, [e.value for e in at.error]


class Finta:
    nome = "sim"
    def chiusura(self, t, d): return (d, {"VHYL.L": 66.0, "^GSPC": 5400.0}.get(t, 66.0))
    def cambio(self, da, a, d): return (d, {("EUR", "CHF"): 0.93, ("USD", "CHF"): 0.80, ("CHF", "EUR"): 1 / 0.93}.get((da, a), 1.0))


def test_flusso_completo():
    db._archivio = db.ArchivioLocale(Path(tempfile.mkdtemp()))
    cc.mercato_reale = lambda manuali=None, snapshot=None: Mercato(Finta())

    at = _at("clienti"); at.run()
    at.text_input(key="nc_nome").set_value("Mario"); at.text_input(key="nc_cogn").set_value("Rossi")
    _bt(at, "Crea cliente").click().run(); _ok(at)
    cid = at.session_state["cli_id"]
    assert dati.carica_cliente(cid)["nome"] == "Mario Rossi"

    at = _at("cliente", cli_id=cid); at.run()
    _bt(at, "Crea").click().run(); _ok(at)
    pf = dati.carica_cliente(cid)["portafogli"][0]
    pre = f"np_{pf['id']}"

    def crea(tipo, sub, nome, valuta, extra=None):
        a = _at("cliente", cli_id=cid); a.run()
        a.radio(key=f"{pre}_tipo").set_value(tipo).run()
        # i menu dipendono dal tipo: nessun sottotipo di un altro tipo
        opz = a.selectbox(key=f"{pre}_sub_{tipo}").options
        assert sub in opz
        if tipo == "Obbligazione":
            assert "Barrier Reverse Convertible" not in opz
        a.selectbox(key=f"{pre}_sub_{tipo}").set_value(sub)
        a.text_input(key=f"{pre}_nome").set_value(nome)
        a.selectbox(key=f"{pre}_val").set_value(valuta)
        for k, (w, v) in (extra or {}).items():
            getattr(a, w)(key=f"{pre}_{k}").set_value(v)
        _bt(a, "Crea prodotto").click().run()
        assert not a.exception

    crea("Prodotto strutturato", "Barrier Reverse Convertible", "6.93% BRC Multi", "EUR", {"ced": ("number_input", 6.93), "bar": ("number_input", 60.0)})
    crea("ETF", "ETF azionario", "Vanguard High Div", "USD", {"t1": ("text_input", "VHYL.L"), "set": ("multiselect", ["Finanziario", "Tecnologia"]), "are": ("multiselect", ["Stati Uniti"])})
    reg = dati.carica_registro()
    brc = next(s for s in reg.strumenti.values() if s["categoria"] == "strutturato")
    etf = next(s for s in reg.strumenti.values() if s["categoria"] == "etf_azioni")
    assert brc["prezzo_in_percento"] and brc["valutazione"] == "scadenza" and not etf["prezzo_in_percento"]
    assert etf["settori"] == {"Finanziario": 0.5, "Tecnologia": 0.5} and etf["aree"] == {"Stati Uniti": 1.0}
    assert len(dati.carica_cliente(cid)["portafogli"][0]["righe"]) == 2

    # valori reali della strategia, poi creazione del portafoglio
    c = dati.carica_cliente(cid); pf = c["portafogli"][0]
    pf["capitale"] = 200000.0; pf["cambi"] = {"USD": 0.8, "EUR": 0.93}
    kb = next(k for k, s in reg.strumenti.items() if s["categoria"] == "strutturato")
    reg.strumenti[kb].update(scadenza="2028-01-06", data_emissione="2026-01-06", frequenza_cedola=4, settori={"Diversificato": 1.0}, aree={"Stati Uniti": 1.0},
                             sottostanti=[{"ticker": "^GSPC", "nome": "S&P 500", "livello_iniziale": 5000.0}])
    dati.salva_registro(reg)
    for r in pf["righe"]:
        r.update(peso_pct=60 if r["strumento"] == kb else 40, prezzo=100.0 if r["strumento"] == kb else 55.0, data="2026-01-06", stato="approvato")
    stg.quantita_da_pesi(pf, reg)
    dati.salva_cliente(c)

    at = _at("cliente", cli_id=cid); at.run(); _ok(at)
    _bt(at, "Prepara il PDF").click().run(); _ok(at)
    assert at.session_state[f"st_pdfb_{pf['id']}"][:4] == b"%PDF"
    at.checkbox(key=f"st_conf_{pf['id']}").check().run()
    _bt(at, "Crea il portafoglio").click().run()
    c = dati.carica_cliente(cid)
    assert c["portafogli"][0]["stato"] == "attivo" and [round(t["importo_cassa"]) for t in c["transazioni"]] == [-129032, -99990]

    at = _at("cliente", cli_id=cid); at.run()
    _bt(at, "Calcola l'andamento").click().run(); _ok(at)

    at = _at("report", cli_id=cid); at.run(); _ok(at)
    _bt(at, "Calcola").click().run(); _ok(at)
    _bt(at, "Genera PDF").click().run(); _ok(at)
    assert at.session_state["rep_pdf"][0][:4] == b"%PDF"
    for v in ("home", "clienti", "archivio_report", "strumenti"):
        a = _at(v, cli_id=cid); a.run(); _ok(a)
