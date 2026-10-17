"""Fonti di riserva per l'ULTIMO prezzo, quando Yahoo non trova il titolo né con ticker né con ISIN.
Ogni fonte restituisce (prezzo, valuta, nome fonte) oppure None. L'ordine di prova segue la riuscita passata: chi trova più prezzi passa avanti.
Sono letture di pagine pubbliche: se un sito cambia struttura quella fonte smette di rispondere e si passa alla successiva."""

from __future__ import annotations

import re
import time
from typing import Optional

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def _num(txt: str) -> Optional[float]:
    t = txt.strip().replace("’", "").replace("'", "").replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# ── TradingView: cerca il simbolo (per ticker o ISIN) e legge l'ultimo prezzo dallo scanner ──
def tv_parse_ricerca(j) -> list[dict]:
    out = []
    for x in j if isinstance(j, list) else []:
        if x.get("symbol") and x.get("exchange"):
            out.append({"simbolo": re.sub(r"</?em>", "", x["symbol"]), "borsa": x["exchange"], "valuta": x.get("currency_code") or ""})
    return out


def tv_parse_scanner(j) -> Optional[tuple[float, str]]:
    try:
        d = j["data"][0]["d"]
        return float(d[0]), str(d[1] or "")
    except (KeyError, IndexError, TypeError, ValueError):
        return None


# Borsa scelta nella scheda → (codici Google Finance, borse TradingView): il prezzo va letto sulla borsa indicata, non su un'altra con lo stesso ticker
CODICI_BORSA = {
    "USA · NYSE / Nasdaq / AMEX": (["NYSE", "NASDAQ", "NYSEARCA", "NYSEAMERICAN", "BATS"], {"NYSE", "NASDAQ", "AMEX", "NYSE ARCA", "CBOE"}),
    "Borsa Italiana (Milano)": (["BIT"], {"MIL", "MTA", "BIT"}), "Xetra (Germania)": (["ETR"], {"XETR", "XETRA"}), "Francoforte": (["FRA"], {"FWB", "FRA"}),
    "Euronext Parigi": (["EPA"], {"EURONEXT", "EPA"}), "Euronext Amsterdam": (["AMS"], {"EURONEXT", "AMS"}), "Euronext Bruxelles": (["EBR"], {"EURONEXT", "EBR"}),
    "Euronext Lisbona": (["ELI"], {"EURONEXT", "ELI"}), "Londra (LSE)": (["LON"], {"LSE", "LON"}), "SIX Swiss Exchange": (["SWX"], {"SIX", "SWX"}), "Madrid": (["BME"], {"BME"}),
    "Vienna": (["VIE"], {"VIE"}), "Stoccolma": (["STO"], {"OMXSTO", "STO"}), "Copenaghen": (["CPH"], {"OMXCOP", "CPH"}), "Helsinki": (["HEL"], {"OMXHEX", "HEL"}),
    "Oslo": (["OSL"], {"OSL"}), "Toronto": (["TSE"], {"TSX", "TSE"}), "Tokyo": (["TYO"], {"TSE", "TYO"}), "Hong Kong": (["HKG"], {"HKEX", "HKG"}), "Sydney (ASX)": (["ASX"], {"ASX"}),
}


class TradingViewFonte:
    nome = "TradingView"

    def ultimo(self, ticker: str, isin: str, valuta: str, borsa: str = "") -> Optional[tuple[float, str, str]]:
        import requests
        tv_borse = CODICI_BORSA.get(borsa, ([], set()))[1]
        for testo in [x for x in ((ticker or "").split(".")[0], isin) if x]:
            try:
                r = requests.get("https://symbol-search.tradingview.com/symbol_search/", params={"text": testo, "type": ""}, headers=UA | {"Origin": "https://www.tradingview.com"}, timeout=12)
                if r.status_code != 200:
                    continue
                cand = tv_parse_ricerca(r.json())
                cand.sort(key=lambda c: (0 if c["borsa"].upper() in tv_borse else 1, 0 if c["valuta"].upper() == (valuta or "").upper() else 1))        # prima la borsa indicata, poi la valuta del prodotto
                if tv_borse and any(c["borsa"].upper() in tv_borse for c in cand):
                    cand = [c for c in cand if c["borsa"].upper() in tv_borse]
                for c in cand[:4]:
                    q = requests.post("https://scanner.tradingview.com/global/scan", json={"symbols": {"tickers": [f"{c['borsa']}:{c['simbolo']}"]}, "columns": ["close", "currency"]}, headers=UA, timeout=12)
                    if q.status_code == 200:
                        res = tv_parse_scanner(q.json())
                        if res:
                            return res[0], res[1] or c["valuta"], self.nome
            except Exception:
                continue
        return None


# ── justETF: per ISIN, utile per ETF europei ──
def justetf_parse(html: str) -> Optional[tuple[float, str]]:
    for rx in (r'class="val"[^>]*>\s*<span>([A-Z]{3})</span>\s*<span>([\d.,]+)</span>', r'"latestQuote"\s*:\s*\{[^}]*?"raw"\s*:\s*([\d.]+)[^}]*?"currency"\s*:\s*"([A-Z]{3})"'):
        m = re.search(rx, html, re.S)
        if m:
            a, b = m.group(1), m.group(2)
            if a.isalpha():
                v = _num(b)
                return (v, a) if v else None
            v = _num(a)
            return (v, b) if v else None
    return None


class JustEtfFonte:
    nome = "justETF"

    def ultimo(self, ticker: str, isin: str, valuta: str, borsa: str = "") -> Optional[tuple[float, str, str]]:
        if not isin:
            return None
        import requests
        try:
            r = requests.get("https://www.justetf.com/it/etf-profile.html", params={"isin": isin}, headers=UA, timeout=15)
            if r.status_code == 200:
                res = justetf_parse(r.text)
                if res:
                    return res[0], res[1], self.nome
        except Exception:
            pass
        return None


# ── Google Finance: pagina pubblica del titolo, quando il simbolo è del tipo TICKER:BORSA ──
def google_parse(html: str) -> Optional[tuple[float, str]]:
    m = re.search(r'data-last-price="([\d.,]+)"', html)
    if not m:
        return None
    v = _num(m.group(1))
    c = re.search(r'data-currency-code="([A-Z]{3})"', html)
    return (v, c.group(1)) if v else None


SUFFISSO_GOOGLE = {"": "NASDAQ", "MI": "BIT", "DE": "ETR", "F": "FRA", "PA": "EPA", "AS": "AMS", "BR": "EBR", "LS": "ELI", "L": "LON", "SW": "SWX", "MC": "BME", "VI": "VIE",
                   "ST": "STO", "CO": "CPH", "HE": "HEL", "OL": "OSL", "TO": "TSE", "T": "TYO", "HK": "HKG", "AX": "ASX"}


def google_parse_ricerca(html: str) -> Optional[tuple[float, str]]:
    """Riquadro del prezzo nella normale ricerca Google («CSSX5 price»): prezzo e valuta."""
    r = google_parse(html)
    if r:
        return r
    m = re.search(r'([\d]{1,3}(?:[\'’.,][\d]{3})*[.,]\d{1,4})\s*(?:<[^>]*>\s*)*(EUR|CHF|USD|GBP|GBX|JPY)\b', html)
    if m:
        v = _num(m.group(1))
        return (v, m.group(2)) if v else None
    return None


class GoogleFinanceFonte:
    nome = "Google Finance"
    BORSE = ["SWX", "BIT", "ETR", "EPA", "AMS", "LON", "NYSEARCA", "NASDAQ", "NYSE", "NYSEAMERICAN", "BATS", "FRA", "EBR", "BME", "VIE", "STO", "CPH", "HEL", "OSL", "TYO", "HKG", "TSE", "ASX"]

    def _una(self, base: str, borsa: str, valuta: str):
        import requests
        try:
            r = requests.get(f"https://www.google.com/finance/quote/{base}:{borsa}", headers=UA | {"Accept-Language": "en"}, timeout=6)
            if r.status_code == 200:
                res = google_parse(r.text)
                if res and (not valuta or res[1].upper() == valuta.upper() or res[1].upper() in ("GBX", "GBP")):
                    return res
        except Exception:
            pass
        return None

    def ultimo(self, ticker: str, isin: str, valuta: str, borsa: str = "") -> Optional[tuple[float, str, str]]:
        import requests
        from concurrent.futures import ThreadPoolExecutor
        base, _, suf = (ticker or "").upper().partition(".")
        scelte = CODICI_BORSA.get(borsa, ([], set()))[0]
        if base and scelte:                                        # borsa indicata: si legge solo lì (un ticker uguale su un'altra borsa è un altro titolo)
            for b in scelte:
                res = self._una(base, b, valuta)
                if res:
                    return res[0], res[1], self.nome
            return None
        if base:
            prima = SUFFISSO_GOOGLE.get(suf)
            if prima:                                              # la borsa indicata dal ticker va provata per prima
                res = self._una(base, prima, valuta)
                if res:
                    return res[0], res[1], self.nome
            altre = [b for b in self.BORSE if b != prima]
            with ThreadPoolExecutor(max_workers=8) as ex:
                for res in ex.map(lambda b: self._una(base, b, valuta), altre):
                    if res:
                        return res[0], res[1], self.nome
        for q in [x for x in (f"{base} {isin}".strip(), isin) if x]:       # come farebbe una persona: ricerca Google di ticker e ISIN
            try:
                r = requests.get("https://www.google.com/search", params={"q": f"{q} price", "hl": "en"}, headers=UA, timeout=8)
                if r.status_code == 200:
                    res = google_parse_ricerca(r.text)
                    if res and (not valuta or res[1].upper() == valuta.upper()):
                        return res[0], res[1], self.nome
            except Exception:
                continue
        return None


# ── Investing.com e Borsa Italiana: ultime spiagge, per ISIN ──
class InvestingFonte:
    nome = "Investing.com"

    def ultimo(self, ticker: str, isin: str, valuta: str, borsa: str = "") -> Optional[tuple[float, str, str]]:
        import requests
        for q in [x for x in (isin, (ticker or "").split(".")[0]) if x]:
            try:
                r = requests.get("https://api.investing.com/api/search/v2/search", params={"q": q}, headers=UA | {"domain-id": "www"}, timeout=10)
                if r.status_code != 200:
                    continue
                quotes = r.json().get("quotes") or []
                for x in quotes[:3]:
                    url = x.get("url")
                    if not url:
                        continue
                    pg = requests.get("https://www.investing.com" + url, headers=UA, timeout=12)
                    m = re.search(r'data-test="instrument-price-last"[^>]*>\s*([\d.,]+)', pg.text)
                    cur = re.search(r'data-test="currency-in-label"[^>]*>\s*([A-Z]{3})', pg.text) or re.search(r'"priceCurrency"\s*:\s*"([A-Z]{3})"', pg.text)
                    v = _num(m.group(1)) if m else None
                    if v:
                        return v, (cur.group(1) if cur else (valuta or "")), self.nome
            except Exception:
                continue
        return None


class BorsaItalianaFonte:
    nome = "Borsa Italiana"

    def ultimo(self, ticker: str, isin: str, valuta: str, borsa: str = "") -> Optional[tuple[float, str, str]]:
        if not isin:
            return None
        import requests
        for tipo in ("etf", "azioni/globalequity", "obbligazioni/euro-obbligazioni", "etf"):
            try:
                url = f"https://www.borsaitaliana.it/borsa/{tipo}/scheda/{isin}.html"
                r = requests.get(url, headers=UA | {"Accept-Language": "it"}, timeout=12)
                if r.status_code != 200:
                    continue
                m = re.search(r'(?:Ultimo (?:prezzo|contratto)|Prezzo ufficiale)[^<]*</span>\s*<span[^>]*>\s*(?:<strong>)?\s*([\d.,]+)', r.text, re.S) \
                    or re.search(r'class="t-text -right[^"]*"[^>]*>\s*<strong>\s*([\d.,]+)', r.text)
                v = _num(m.group(1)) if m else None
                if v:
                    return v, valuta or "EUR", self.nome
            except Exception:
                continue
        return None


class CatenaRiserva:
    """Prova le fonti in ordine di riuscita (le statistiche vivono nella cache condivisa, quindi durano finché l'app è accesa)."""

    def __init__(self, fonti=None, statistiche: dict | None = None):
        self.fonti = fonti or [GoogleFinanceFonte(), TradingViewFonte(), JustEtfFonte()]
        self.stat = statistiche if statistiche is not None else _STAT

    def ordinate(self):
        return list(self.fonti)                        # ordine fisso voluto: Google Finance, TradingView, justETF

    def ultimo(self, ticker: str, isin: str, valuta: str, borsa: str = ""):
        for f in self.ordinate():
            try:
                try:
                    r = f.ultimo(ticker, isin, valuta, borsa)
                except TypeError:                              # fonte senza il parametro «borsa»
                    r = f.ultimo(ticker, isin, valuta)
            except Exception:
                r = None
            st = self.stat.setdefault(f.nome, [0, 0])
            if r:
                st[0] += 1
                return r
            st[1] += 1
        return None


_STAT: dict = {}
