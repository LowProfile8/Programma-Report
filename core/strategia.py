"""Strategia di un portafoglio: prodotti proposti con pesi, prezzi e quantità ideali; poi, a esecuzione avvenuta, valori reali e creazione del portafoglio."""

from __future__ import annotations

import urllib.parse
import uuid
from datetime import date

from core.config import CATEGORIE

TIPI_INCASSO = {"cedola": "Cedola", "interesse": "Interessi", "dividendo": "Dividendo", "premio_opzione": "Premio opzione"}
TIPI_COSTO_UI = {"costo_custodia": "Diritti di custodia", "costo": "Spese bancarie / commissioni", "imposta": "Imposte"}


def lordo(quantita: float, prezzo: float, in_percento: bool) -> float:
    """Controvalore: quantità (o nominale) × prezzo; il prezzo è in % del nominale per obbligazioni e strutturati."""
    return (quantita or 0.0) * (prezzo or 0.0) / (100.0 if in_percento else 1.0)


def quantita_da_investito(investito: float, prezzo: float, in_percento: bool) -> float:
    unit = (prezzo or 0.0) / (100.0 if in_percento else 1.0)
    return investito / unit if unit else 0.0


def cambio(pf: dict, valuta: str, base: str, cerca=None) -> tuple[float, bool]:
    """(tasso, affidabile). Priorità: tasso inserito a mano, poi mercato (se disponibile)."""
    if not valuta or valuta == base:
        return 1.0, True
    man = (pf.get("cambi") or {}).get(valuta)
    if man:
        return float(man), True
    if cerca:
        try:
            r = cerca(valuta, base)
            if r:
                return float(r), True
        except Exception:
            pass
    return 1.0, False


# ───────────────────────── il portafoglio È la strategia: ogni acquisto è una riga ───────────────────────
def aggiungi_acquisto(cliente: dict, pf: dict, reg, chiave: str, data: str, prezzo: float, commissioni: float = 0.0, *,
                      investito: float | None = None, quantita: float | None = None) -> dict:
    """Registra un acquisto nel portafoglio. Si dà l'importo investito O la quantità/nominale: l'altro si calcola dal prezzo."""
    s = reg.strumenti[chiave]
    pct = bool(s.get("prezzo_in_percento"))
    if quantita is None:
        quantita = quantita_da_investito(investito or 0.0, prezzo, pct)
    lord = lordo(quantita, prezzo, pct)
    tx = {"id": f"strategia:{pf['id']}:{uuid.uuid4().hex[:8]}", "data": data, "data_valuta": data, "tipo": "acquisto", "titolo": f"Acquisto {s['nome']}", "valuta": s["valuta"],
          "importo_cassa": -(lord + commissioni), "quantita": quantita, "prezzo": prezzo, "prezzo_in_percento": pct, "importo_lordo": lord, "commissione": commissioni,
          "tasse": 0.0, "rif": "", "banca": "", "conto": "", "strumento": chiave, "fonte": "strategia", "portafoglio": pf["id"]}
    cliente["transazioni"].append(tx)
    pf["stato"] = "attivo"
    if s.get("valutazione") == "manuale" and not s.get("nav_manuale"):
        s["nav_manuale"] = [{"data": data, "nav": prezzo}]            # valore iniziale = prezzo d'acquisto, poi lo aggiorni tu
    return tx


def modifica_acquisto(tx: dict, s: dict, *, data=None, prezzo=None, quantita=None, investito=None, commissioni=None):
    """Aggiorna un acquisto. Se cambia l'investito si ricalcola la quantità; altrimenti l'investito segue quantità × prezzo."""
    pct = bool(s.get("prezzo_in_percento"))
    prezzo = tx.get("prezzo") if prezzo is None else prezzo
    comm = (tx.get("commissione") or 0.0) if commissioni is None else commissioni
    if investito is not None and quantita is None:
        quantita = quantita_da_investito(investito, prezzo, pct)
    quantita = tx.get("quantita") if quantita is None else quantita
    lord = lordo(quantita, prezzo, pct)
    tx.update(prezzo=prezzo, quantita=quantita, prezzo_in_percento=pct, importo_lordo=lord, commissione=comm, tasse=0.0, importo_cassa=-(lord + comm))
    if data:
        tx["data"] = tx["data_valuta"] = data


def registra_incasso(cliente: dict, pf: dict, reg, chiave: str, tipo: str, data: str, importo: float, imposta: float = 0.0, nota: str = "") -> None:
    s = reg.strumenti[chiave]
    base = {"data_valuta": data, "valuta": s["valuta"], "quantita": None, "prezzo": None, "prezzo_in_percento": False, "importo_lordo": None, "commissione": 0.0, "tasse": 0.0,
            "rif": "", "banca": "", "conto": "", "strumento": chiave, "fonte": "manuale", "portafoglio": pf["id"]}
    cliente["transazioni"].append({**base, "id": f"manuale:{uuid.uuid4().hex[:10]}", "data": data, "tipo": tipo, "titolo": f"{TIPI_INCASSO.get(tipo, tipo)} {s['nome']}" + (f" ({nota})" if nota else ""), "importo_cassa": importo})
    if imposta:
        cliente["transazioni"].append({**base, "id": f"manuale:{uuid.uuid4().hex[:10]}", "data": data, "tipo": "imposta", "titolo": f"Imposta su {TIPI_INCASSO.get(tipo, tipo).lower()} {s['nome']}", "importo_cassa": -abs(imposta)})


def registra_costo(cliente: dict, pf: dict, tipo: str, data: str, importo: float, valuta: str, descrizione: str = "") -> None:
    cliente["transazioni"].append({"id": f"manuale:{uuid.uuid4().hex[:10]}", "data": data, "data_valuta": data, "tipo": tipo, "titolo": descrizione or TIPI_COSTO_UI.get(tipo, tipo),
                                   "valuta": valuta, "importo_cassa": -abs(importo), "quantita": None, "prezzo": None, "prezzo_in_percento": False, "importo_lordo": None,
                                   "commissione": 0.0, "tasse": 0.0, "rif": "", "banca": "", "conto": "", "strumento": "", "fonte": "manuale", "portafoglio": pf["id"]})


def calcola(cliente: dict, pf: dict, reg, cerca=None) -> dict:
    """Riepilogo del portafoglio a costo: una riga per acquisto, pesi, esposizioni, reddito cedolare atteso."""
    from core import dati
    v = dati.vista_portafoglio(cliente, pf["id"])
    base = pf["valuta"]
    netto: dict[str, float] = {}
    for t in v["transazioni"]:
        if t["tipo"] in ("acquisto", "vendita", "rimborso") and t.get("strumento"):
            seg = 1 if t["tipo"] == "acquisto" else -1
            netto[t["strumento"]] = netto.get(t["strumento"], 0.0) + seg * (t.get("quantita") or 0.0)
    righe, avvisi = [], []
    for t in sorted(v["transazioni"], key=lambda x: x["data"]):
        s = reg.strumenti.get(t.get("strumento"))
        if t["tipo"] != "acquisto" or not s:
            continue
        comm = (t.get("commissione") or 0.0) + (t.get("tasse") or 0.0)
        inv = t.get("importo_lordo") if t.get("importo_lordo") is not None else -t["importo_cassa"] - comm
        tasso, ok = cambio(pf, s.get("valuta", base), base, cerca)
        if not ok:
            m = f"Cambio {s.get('valuta')}→{base} non disponibile: importi non convertiti. Inseriscilo a mano."
            if m not in avvisi:
                avvisi.append(m)
        righe.append({"id": t["id"], "strumento": t["strumento"], "nome": s["nome"], "isin": s.get("isin", ""), "categoria": s.get("categoria"), "sottocategoria": s.get("sottocategoria", ""),
                      "valuta": s.get("valuta", base), "data": t["data"], "quantita": t.get("quantita") or 0.0, "prezzo": t.get("prezzo"), "commissioni": comm, "importo": inv,
                      "importo_base": inv * tasso, "tasso": tasso, "attivo": netto.get(t["strumento"], 0.0) > 1e-9, "fonte": t.get("fonte", ""),
                      "cedola_annua_pct": s.get("cedola_annua_pct"), "scadenza": s.get("scadenza", ""), "barriera_pct": s.get("barriera_pct"), "protezione_pct": s.get("protezione_pct"),
                      "sottostanti": s.get("sottostanti", []), "settori": s.get("settori") or {}, "aree": s.get("aree") or {}, "prezzo_in_percento": bool(s.get("prezzo_in_percento"))})
    attive = [x for x in righe if x["attivo"]]
    tot = sum(x["importo_base"] for x in attive)
    for x in righe:
        x["peso_eff_pct"] = 100.0 * x["importo_base"] / tot if (tot and x["attivo"]) else 0.0
    allocazione, valute, settori, aree = {}, {}, {}, {}
    reddito = 0.0
    for x in attive:
        allocazione[x["categoria"]] = allocazione.get(x["categoria"], 0.0) + x["importo_base"]
        valute[x["valuta"]] = valute.get(x["valuta"], 0.0) + x["importo_base"]
        for dest, pesi in ((settori, x["settori"]), (aree, x["aree"])):
            if pesi:
                for k, w in pesi.items():
                    dest[k] = dest.get(k, 0.0) + x["importo_base"] * w
            else:
                dest["Non classificato"] = dest.get("Non classificato", 0.0) + x["importo_base"]
        if x["cedola_annua_pct"]:
            reddito += (x["quantita"] if x["prezzo_in_percento"] else x["importo"]) * x["tasso"] * x["cedola_annua_pct"] / 100.0
    comm = sum(x["commissioni"] * x["tasso"] for x in attive)
    return {"righe": righe, "attive": attive, "totale": tot, "commissioni": comm, "allocazione": allocazione, "valute": valute, "settori": settori, "aree": aree,
            "reddito_annuo": reddito, "rendimento_cedolare": reddito / tot if tot else None, "avvisi": avvisi,
            "capitale": pf.get("capitale", 0.0), "liquidita_residua": (pf.get("capitale", 0.0) - tot - comm) if pf.get("capitale") else None}


# ───────────────────────── analisi con Claude ─────────────────────────
PUNTI_ANALISI = [
    "Rating e target price degli analisti sui singoli titoli/emittenti e sui sottostanti",
    "Conti economici e bilanci aziendali (ricavi, margini, utile, indebitamento, flussi di cassa)",
    "Struttura e qualità del management",
    "Value proposition e posizionamento rispetto ai concorrenti",
    "Previsioni a 12, 24 e 36 mesi (scenari base, positivo, negativo)",
]


def testo_analisi(cliente: dict, pf: dict, calc: dict) -> str:
    e = lambda x: f"{x:,.0f}".replace(",", "’")
    righe = []
    for x in calc["attive"]:
        extra = []
        if x.get("cedola_annua_pct"): extra.append(f"cedola {x['cedola_annua_pct']:g}% annua")
        if x.get("scadenza"): extra.append(f"scadenza {x['scadenza']}")
        if x.get("barriera_pct"): extra.append(f"barriera {x['barriera_pct']:g}%")
        if x.get("protezione_pct"): extra.append(f"protezione capitale {x['protezione_pct']:g}%")
        if x.get("sottostanti"): extra.append("sottostanti: " + ", ".join(f"{u.get('nome') or u.get('ticker')}" for u in x["sottostanti"]))
        righe.append(f"- {x['nome']} [{x['isin'] or 'ISIN n.d.'}] · {CATEGORIE.get(x['categoria'], x['categoria'])}{' / ' + x['sottocategoria'] if x['sottocategoria'] else ''} · "
                     f"peso {x['peso_eff_pct']:.1f}% · {x['valuta']} {e(x['importo'])}" + (" · " + "; ".join(extra) if extra else ""))
    sett = ", ".join(f"{k} {100 * v / calc['totale']:.0f}%" for k, v in sorted(calc["settori"].items(), key=lambda kv: -kv[1])) if calc["totale"] else "n.d."
    aree = ", ".join(f"{k} {100 * v / calc['totale']:.0f}%" for k, v in sorted(calc["aree"].items(), key=lambda kv: -kv[1])) if calc["totale"] else "n.d."
    punti = "\n".join(f"{i}. {p}" for i, p in enumerate(PUNTI_ANALISI, 1))
    return (
        f"Sei un analista finanziario senior. Analizza la strategia di investimento qui sotto (profilo di rischio {cliente.get('rischio', '-')}/5, valuta {pf['valuta']}, "
        f"capitale {pf['valuta']} {e(pf['capitale'])}, data {date.today().strftime('%d.%m.%Y')}). Usa la ricerca web per i dati e le notizie più recenti.\n\n"
        f"STRATEGIA «{pf['nome']}»\n" + "\n".join(righe) + f"\n\nEsposizione settoriale: {sett}\nEsposizione geografica: {aree}\n\n"
        f"Per ogni prodotto/emittente/sottostante valuta:\n{punti}\n\n"
        "Conclusione: dai un voto complessivo alla strategia da 0 a 100 (100 = strategia perfetta rispetto al momento macroeconomico e alle ultime notizie), "
        "motivalo, e se non è 100 indica i consigli concreti: nuovi acquisti da valutare e modifiche al portafoglio attuale (cosa ridurre, sostituire o aggiungere, con motivazione e rischi). "
        "Distingui fatti verificati da tue valutazioni e cita le fonti."
    )


def link_claude(testo: str) -> str:
    return "https://claude.ai/new?q=" + urllib.parse.quote(testo[:6000])
