"""Indici di borsa in diretta (Yahoo Finance): prezzo e variazione giornaliera di tutti gli indici, senza barra scorrevole."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

INDICI = [("URTH", "MSCI World (URTH)"), ("^GSPC", "S&P 500"), ("^NDX", "Nasdaq 100"), ("^STOXX50E", "Euro Stoxx 50"), ("FTSEMIB.MI", "FTSE MIB"),
          ("^IBEX", "IBEX 35"), ("^GDAXI", "DAX"), ("^FCHI", "CAC 40"), ("^AEX", "AEX"), ("^FTSE", "FTSE 100")]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def parse_chart(j: dict) -> tuple[float, float] | None:
    """(ultimo prezzo, variazione %) da una risposta chart di Yahoo."""
    try:
        r = j["chart"]["result"][0]
        m = r["meta"]
        px = m.get("regularMarketPrice")
        prev = m.get("chartPreviousClose") or m.get("previousClose")
        if px is None:
            cl = [x for x in r["indicators"]["quote"][0]["close"] if x is not None]
            px, prev = cl[-1], (cl[-2] if len(cl) > 1 else None)
        if not prev:
            return float(px), 0.0
        return float(px), float(px) / float(prev) - 1
    except Exception:
        return None


def _uno(sim: str):
    import requests
    for host in ("query1", "query2"):
        try:
            r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{sim}", params={"range": "5d", "interval": "1d"}, headers=UA, timeout=8)
            if r.status_code == 200:
                v = parse_chart(r.json())
                if v:
                    return v
        except Exception:
            continue
    return None


def quotazioni() -> list[dict]:
    with ThreadPoolExecutor(max_workers=len(INDICI)) as ex:
        res = list(ex.map(lambda x: _uno(x[0]), INDICI))
    return [{"simbolo": s, "nome": n, "prezzo": r[0] if r else None, "var": r[1] if r else None} for (s, n), r in zip(INDICI, res)]
