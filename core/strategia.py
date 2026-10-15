"""Strategia di un portafoglio: prodotti proposti con pesi, prezzi e quantità ideali; poi, a esecuzione avvenuta, valori reali e creazione del portafoglio."""

from __future__ import annotations

import math
import urllib.parse
import uuid
from datetime import date

from core.config import CATEGORIE

STATI = {"proposto": "Proposto", "approvato": "Approvato dal cliente", "scartato": "Scartato", "eseguito": "Acquistato"}


def nuova_riga(chiave: str) -> dict:
    return {"id": uuid.uuid4().hex[:8], "strumento": chiave, "peso_pct": 0.0, "prezzo": 0.0, "quantita": 0.0, "commissioni": 0.0,
            "data": date.today().isoformat(), "stato": "proposto", "nota": ""}


def importo_riga(riga: dict, s: dict) -> float:
    """Controvalore in valuta del prodotto: quantità × prezzo (prezzo in % del nominale per obbligazioni e strutturati)."""
    q, p = riga.get("quantita") or 0.0, riga.get("prezzo") or 0.0
    return q * p / (100.0 if s.get("prezzo_in_percento") else 1.0)


def cambio(pf: dict, valuta: str, base: str, cerca=None) -> tuple[float, bool]:
    """(tasso, affidabile). Priorità: tasso inserito a mano nella strategia, poi mercato (se disponibile)."""
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


def quantita_da_pesi(pf: dict, reg, cerca=None) -> None:
    """Calcola per ogni riga la quantità intera che si avvicina al peso voluto (sul capitale della strategia)."""
    for r in pf["righe"]:
        s = reg.strumenti.get(r["strumento"])
        if not s or not r.get("prezzo") or r.get("stato") == "scartato":
            continue
        tasso, _ = cambio(pf, s.get("valuta", pf["valuta"]), pf["valuta"], cerca)
        target = pf["capitale"] * (r.get("peso_pct") or 0) / 100.0 / (tasso or 1.0)
        unitario = r["prezzo"] / (100.0 if s.get("prezzo_in_percento") else 1.0)
        r["quantita"] = float(math.floor(target / unitario)) if unitario else 0.0


def calcola(pf: dict, reg, cerca=None, solo_attive: bool = True) -> dict:
    """Riepilogo numerico della strategia: righe arricchite, totali, esposizioni, reddito atteso."""
    base = pf["valuta"]
    righe, avvisi = [], []
    for r in pf["righe"]:
        s = reg.strumenti.get(r["strumento"])
        if not s or (solo_attive and r.get("stato") == "scartato"):
            continue
        imp = importo_riga(r, s)
        tasso, ok = cambio(pf, s.get("valuta", base), base, cerca)
        if not ok:
            avvisi.append(f"Cambio {s.get('valuta')}→{base} non disponibile: importi di {s['nome']} non convertiti. Inseriscilo a mano nella strategia.")
        righe.append({**r, "nome": s["nome"], "isin": s.get("isin", ""), "categoria": s.get("categoria"), "sottocategoria": s.get("sottocategoria", ""),
                      "valuta": s.get("valuta", base), "importo": imp, "importo_base": imp * tasso, "tasso": tasso,
                      "cedola_annua_pct": s.get("cedola_annua_pct"), "scadenza": s.get("scadenza", ""), "barriera_pct": s.get("barriera_pct"),
                      "protezione_pct": s.get("protezione_pct"), "sottostanti": s.get("sottostanti", []), "settori": s.get("settori") or {}, "aree": s.get("aree") or {},
                      "prezzo_in_percento": bool(s.get("prezzo_in_percento"))})
    tot = sum(x["importo_base"] for x in righe)
    base_pesi = tot or 1.0
    for x in righe:
        x["peso_eff_pct"] = 100.0 * x["importo_base"] / base_pesi
    allocazione: dict[str, float] = {}
    valute: dict[str, float] = {}
    settori: dict[str, float] = {}
    aree: dict[str, float] = {}
    reddito = 0.0
    for x in righe:
        allocazione[x["categoria"]] = allocazione.get(x["categoria"], 0.0) + x["importo_base"]
        valute[x["valuta"]] = valute.get(x["valuta"], 0.0) + x["importo_base"]
        for dest, pesi in ((settori, x["settori"]), (aree, x["aree"])):
            if pesi:
                for k, w in pesi.items():
                    dest[k] = dest.get(k, 0.0) + x["importo_base"] * w
            else:
                dest["Non classificato"] = dest.get("Non classificato", 0.0) + x["importo_base"]
        if x["cedola_annua_pct"]:
            reddito += x["importo_base"] * x["cedola_annua_pct"] / 100.0 if not x["prezzo_in_percento"] else x["quantita"] * x["tasso"] * x["cedola_annua_pct"] / 100.0
    comm = sum((x.get("commissioni") or 0) for x in righe)
    return {"righe": righe, "totale": tot, "commissioni": comm, "allocazione": allocazione, "valute": valute, "settori": settori, "aree": aree,
            "reddito_annuo": reddito, "rendimento_cedolare": reddito / tot if tot else None, "avvisi": avvisi,
            "peso_totale_pct": sum((r.get("peso_pct") or 0) for r in pf["righe"] if r.get("stato") != "scartato"),
            "capitale": pf["capitale"], "liquidita_residua": pf["capitale"] - tot - comm}


def problemi(pf: dict, reg) -> list[str]:
    out = []
    for r in pf["righe"]:
        if r.get("stato") in ("scartato", "eseguito"):
            continue
        s = reg.strumenti.get(r["strumento"], {})
        if not r.get("prezzo"):
            out.append(f"{s.get('nome', r['strumento'])}: manca il prezzo")
        if not r.get("quantita"):
            out.append(f"{s.get('nome', r['strumento'])}: manca la quantità")
    return out


def crea_portafoglio(cliente: dict, pf: dict, reg) -> int:
    """Trasforma le righe approvate in acquisti reali (con i prezzi e le quantità inseriti). Il portafoglio diventa attivo."""
    n = 0
    for r in pf["righe"]:
        if r.get("stato") != "approvato":
            continue
        s = reg.strumenti[r["strumento"]]
        lordo = importo_riga(r, s)
        comm = float(r.get("commissioni") or 0)
        cliente["transazioni"].append({
            "id": f"strategia:{pf['id']}:{r['id']}", "data": r["data"], "data_valuta": r["data"], "tipo": "acquisto", "titolo": f"Acquisto {s['nome']}",
            "valuta": s["valuta"], "importo_cassa": -(lordo + comm), "quantita": r["quantita"], "prezzo": r["prezzo"], "prezzo_in_percento": bool(s.get("prezzo_in_percento")),
            "importo_lordo": lordo, "commissione": comm, "tasse": 0.0, "rif": "", "banca": "", "conto": "", "strumento": r["strumento"], "fonte": "strategia", "portafoglio": pf["id"]})
        r["stato"] = "eseguito"
        n += 1
    if n or pf["stato"] == "strategia":
        pf["stato"] = "attivo"
    return n


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
    for x in calc["righe"]:
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
