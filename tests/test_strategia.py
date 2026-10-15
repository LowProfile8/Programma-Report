import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import dati, db, strategia as stg
from core.anagrafica import Registro
from core.strategia_pdf import genera_pdf_strategia


def _setup():
    db._archivio = db.ArchivioLocale(Path(tempfile.mkdtemp()))
    c = dati.nuovo_cliente("Mario", "CHF", 3, cognome="Rossi")
    reg = Registro()
    k1 = reg.assicura(isin="CH0000000001", nome="6.93% BRC Multi", valuta="EUR", pct=True)
    reg.strumenti[k1].update(categoria="strutturato", sottocategoria="Barrier Reverse Convertible", valutazione="scadenza", cedola_annua_pct=6.93, scadenza="2028-01-06",
                             barriera_pct=60.0, settori={"Diversificato": 1.0}, aree={"Europa": 0.5, "Stati Uniti": 0.5}, prezzo_in_percento=True)
    k2 = reg.assicura(isin="IE00B8GKDB10", nome="Vanguard High Div ETF", valuta="USD")
    reg.strumenti[k2].update(categoria="etf_azioni", sottocategoria="ETF azionario", valutazione="mercato", ticker_mercato="VHYL.L", settori={"Finanziario": 0.5, "Tecnologia": 0.5}, aree={"Stati Uniti": 1.0})
    pf = dati.nuovo_portafoglio(c, "Strategia 1", 100000)
    pf["cambi"] = {"USD": 0.8, "EUR": 0.93}
    for k, peso, prezzo in ((k1, 60, 100.0), (k2, 40, 50.0)):
        r = stg.nuova_riga(k); r.update(peso_pct=peso, prezzo=prezzo); pf["righe"].append(r)
    return c, reg, pf, k1, k2


def test_quantita_e_calcolo():
    c, reg, pf, k1, k2 = _setup()
    stg.quantita_da_pesi(pf, reg)
    assert pf["righe"][0]["quantita"] == 64516          # 60'000 CHF / 0.93 = 64'516.1 EUR nominali al 100%
    calc = stg.calcola(pf, reg)
    assert abs(calc["totale"] - sum(x["importo_base"] for x in calc["righe"])) < 1e-6
    assert abs(sum(x["peso_eff_pct"] for x in calc["righe"]) - 100) < 1e-6
    assert calc["reddito_annuo"] > 0 and calc["aree"]["Stati Uniti"] > 0
    assert "peso 60" in stg.testo_analisi(c, pf, calc) or "peso" in stg.testo_analisi(c, pf, calc)
    assert genera_pdf_strategia(c, pf, calc)[:4] == b"%PDF"


def test_crea_portafoglio_e_sostituzione_da_estratto():
    c, reg, pf, k1, k2 = _setup()
    stg.quantita_da_pesi(pf, reg)
    for r in pf["righe"]:
        r["stato"] = "approvato"; r["data"] = "2026-01-06"
    assert stg.crea_portafoglio(c, pf, reg) == 2 and pf["stato"] == "attivo"
    v = dati.vista_portafoglio(c, pf["id"])
    assert len(v["transazioni"]) == 2 and all(t["importo_cassa"] < 0 for t in v["transazioni"])
    # un estratto con lo stesso acquisto (prezzo reale diverso) sostituisce quello della strategia
    est = {"banca": "PostFinance", "conto": "X", "movimenti": [{"data": "2026-01-07", "data_valuta": "2026-01-07", "tipo": "acquisto", "titolo": "BRC", "valuta": "EUR", "importo_cassa": -64000.0,
           "quantita": 64516.0 + 0, "prezzo": 99.2, "prezzo_in_percento": True, "importo_lordo": 64000.0, "commissione": 0.0, "tasse": 0.0, "rif": "R1", "isin": "CH0000000001", "nome": "BRC", "simbolo": ""}],
           "conti": {"EUR": {"saldo_finale": 0.0}}, "controlli": [], "avvisi": [], "quadra": True, "periodo_da": "2026-01-01", "periodo_a": "2026-01-31"}
    c["transazioni"][0]["quantita"] = 64516.0
    r = dati.importa_in_portafoglio(c, pf["id"], dati.importa_estratto, est, reg)
    v = dati.vista_portafoglio(c, pf["id"])
    brc = [t for t in v["transazioni"] if t["strumento"] == k1]
    assert len(brc) == 1 and brc[0]["fonte"] == "estratto"


def test_portafogli_separati():
    c, reg, pf, k1, k2 = _setup()
    pf2 = dati.nuovo_portafoglio(c, "Altro")
    c["transazioni"].append({"id": "a", "data": "2026-01-01", "tipo": "deposito", "valuta": "CHF", "importo_cassa": 10, "portafoglio": pf2["id"]})
    assert len(dati.vista_portafoglio(c, pf2["id"])["transazioni"]) == 1 and not dati.vista_portafoglio(c, pf["id"])["transazioni"]
