"""Dati di mercato: prezzi, cambi e sottostanti, con DOPPIO CONTROLLO.

Meccanismo a tre livelli (tutto gratuito):
  1. Fonte principale (Yahoo Finance) e fonte di controllo indipendente (Stooq per i titoli, BCE/Frankfurter
     per i cambi). Se divergono oltre la tolleranza la posizione finisce in «da verificare» e il report non
     si genera finché non si conferma o si corregge a mano il prezzo.
  2. Controllo interno: il prezzo pagato in un acquisto/vendita dell'estratto conto deve essere vicino alla
     chiusura di mercato di quel giorno. Se non lo è, quasi sempre il ticker è sbagliato.
  3. Congelamento: i prezzi usati in un report vengono salvati con il report (data e fonte). Riaprendolo
     si rivedono gli stessi numeri, anche se la fonte nel frattempo li ha corretti.
Le fonti sono oggetti intercambiabili: i test usano fonti finte, l'app usa quelle reali.
"""

from __future__ import annotations

import io
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Protocol

from core.config import CACHE_PREZZI, TOLLERANZA_PREZZI

TOLLERANZA_CAMBI = 0.005
TOLLERANZA_ACQUISTO = 0.03       # il prezzo di un acquisto può stare dentro il range del giorno
FINESTRA_GIORNI = 7              # si accetta l'ultima chiusura entro 7 giorni (festivi, weekend)


class Fonte(Protocol):
    nome: str

    def chiusura(self, ticker: str, data: str) -> Optional[tuple[str, float]]: ...
    def cambio(self, da: str, a: str, data: str) -> Optional[tuple[str, float]]: ...


# ───────────────────────── fonti reali ─────────────────────────
class YahooFonte:
    nome = "Yahoo Finance"

    def _storico(self, ticker: str, data: str):
        import yfinance as yf
        d = date.fromisoformat(data)
        h = yf.Ticker(ticker).history(start=(d - timedelta(days=FINESTRA_GIORNI + 3)).isoformat(),
                                      end=(d + timedelta(days=1)).isoformat(), auto_adjust=False)
        return h

    def chiusura(self, ticker, data):
        try:
            h = self._storico(ticker, data)
            if h is None or h.empty:
                return None
            riga = h["Close"].dropna()
            if riga.empty:
                return None
            return riga.index[-1].date().isoformat(), float(riga.iloc[-1])
        except Exception:
            return None

    def intervallo(self, ticker: str, data: str) -> Optional[tuple[float, float]]:
        """(minimo, massimo) del giorno: serve al controllo interno sugli acquisti."""
        try:
            h = self._storico(ticker, data)
            r = h[h.index.date == date.fromisoformat(data)]
            if r.empty:
                return None
            return float(r["Low"].iloc[0]), float(r["High"].iloc[0])
        except Exception:
            return None

    def valuta_ticker(self, ticker: str) -> Optional[str]:
        try:
            import yfinance as yf
            return str(yf.Ticker(ticker).fast_info["currency"]).upper()
        except Exception:
            return None

    def cambio(self, da, a, data):
        return self.chiusura(f"{da}{a}=X", data)


class StooqFonte:
    nome = "Stooq"

    def chiusura(self, ticker, data):
        try:
            import requests
            d = date.fromisoformat(data)
            url = ("https://stooq.com/q/d/l/?s=%s&d1=%s&d2=%s&i=d" %
                   (ticker.lower(), (d - timedelta(days=FINESTRA_GIORNI + 3)).strftime("%Y%m%d"), d.strftime("%Y%m%d")))
            r = requests.get(url, timeout=15)
            if r.status_code != 200 or "Date" not in r.text:
                return None
            import pandas as pd
            df = pd.read_csv(io.StringIO(r.text))
            if df.empty:
                return None
            ultima = df.iloc[-1]
            return str(ultima["Date"]), float(ultima["Close"])
        except Exception:
            return None

    def cambio(self, da, a, data):
        return self.chiusura(f"{da}{a}", data)


class BceFonte:
    """Cambi di riferimento BCE tramite Frankfurter (gratuito, senza chiave)."""
    nome = "BCE (Frankfurter)"

    def chiusura(self, ticker, data):
        return None

    def cambio(self, da, a, data):
        try:
            import requests
            r = requests.get(f"https://api.frankfurter.app/{data}", params={"from": da, "to": a}, timeout=15)
            if r.status_code != 200:
                return None
            j = r.json()
            return j["date"], float(j["rates"][a])
        except Exception:
            return None


# ───────────────────────── cache ─────────────────────────
class Cache:
    def __init__(self, percorso: Path | None = CACHE_PREZZI):
        self.percorso = percorso
        self.dati: dict = {}
        if percorso and percorso.exists():
            try:
                self.dati = json.loads(percorso.read_text())
            except Exception:
                self.dati = {}

    def get(self, chiave):
        return self.dati.get(chiave)

    def set(self, chiave, valore):
        self.dati[chiave] = valore

    def salva(self):
        if self.percorso:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            self.percorso.write_text(json.dumps(self.dati))


# ───────────────────────── mercato ─────────────────────────
class Mercato:
    """Fornisce a performance.Contesto le tre funzioni: fx, prezzo, spot. Registra cosa ha usato."""

    def __init__(self, principale: Fonte, controllo_titoli: Optional[Fonte] = None, controllo_cambi: Optional[Fonte] = None,
                 cache: Cache | None = None, manuali: dict | None = None, snapshot: dict | None = None):
        self.principale, self.controllo_titoli, self.controllo_cambi = principale, controllo_titoli, controllo_cambi
        self.cache = cache or Cache(None)
        self.manuali = manuali or {}          # "chiave@data" -> prezzo confermato dall'utente
        self.snapshot = snapshot or {}        # prezzi già congelati in un report salvato
        self.registro: dict[str, dict] = {}   # ciò che è stato usato (diventa lo snapshot)
        self.cambi_usati: dict[str, dict] = {}

    # ── cache trasparente ──
    def _cercato(self, fonte: Fonte, tipo: str, args: tuple, data: str):
        k = f"{fonte.nome}|{tipo}|{'|'.join(args)}|{data}"
        hit = self.cache.get(k)
        if hit is not None:
            return tuple(hit) if hit else None
        res = fonte.chiusura(args[0], data) if tipo == "px" else fonte.cambio(args[0], args[1], data)
        if res is not None:                   # non si memorizzano i buchi: potrebbero essere un guasto momentaneo
            self.cache.set(k, list(res))
        return res

    # ── prezzi ──
    def prezzo(self, strumento: dict, data: str) -> dict:
        chiave = f"{strumento['chiave']}@{data}"
        if chiave in self.manuali:
            return self._registra(chiave, {"prezzo": float(self.manuali[chiave]), "fonte": "inserito a mano", "stato": "manuale"})
        if chiave in self.snapshot:
            return self._registra(chiave, dict(self.snapshot[chiave]))
        t1, t2 = strumento.get("ticker_mercato"), strumento.get("ticker_controllo")
        if not t1:
            return self._registra(chiave, {"prezzo": None, "fonte": "", "stato": "ticker_mancante"})
        p1 = self._cercato(self.principale, "px", (t1,), data)
        if p1 is None:
            return self._registra(chiave, {"prezzo": None, "fonte": "", "stato": "non_trovato"})
        out = {"prezzo": p1[1], "fonte": f"{self.principale.nome} ({p1[0]})", "stato": "unica_fonte"}
        if self.controllo_titoli and t2:
            p2 = self._cercato(self.controllo_titoli, "px", (t2,), data)
            if p2 is None:
                out["stato"] = "controllo_non_disponibile"
            else:
                scarto = abs(p1[1] - p2[1]) / p1[1] if p1[1] else 1.0
                out.update(prezzo_controllo=p2[1], scarto=scarto, fonte_controllo=f"{self.controllo_titoli.nome} ({p2[0]})")
                out["stato"] = "ok" if scarto <= TOLLERANZA_PREZZI else "discrepanza"
        return self._registra(chiave, out)

    def _registra(self, chiave, r):
        self.registro[chiave] = r
        return r

    def spot(self, ticker: str, data: str) -> Optional[float]:
        r = self._cercato(self.principale, "px", (ticker,), data)
        return r[1] if r else None

    # ── cambi ──
    def fx(self, da: str, a: str, data: str) -> Optional[float]:
        if da == a:
            return 1.0
        k = f"{da}{a}@{data}"
        if k in self.manuali:
            return float(self.manuali[k])
        if k in self.snapshot:
            return float(self.snapshot[k]["tasso"])
        ctrl = self.controllo_cambi or self.controllo_titoli
        p = self._cercato(ctrl, "fx", (da, a), data) if ctrl else None       # BCE come riferimento ufficiale
        s = self._cercato(self.principale, "fx", (da, a), data)
        scelta = p or s
        if scelta is None:
            return None
        stato = "unica_fonte"
        if p and s:
            scarto = abs(p[1] - s[1]) / p[1]
            stato = "ok" if scarto <= TOLLERANZA_CAMBI else "discrepanza"
        self.cambi_usati[k] = {"tasso": scelta[1], "fonte": (ctrl.nome if p else self.principale.nome), "stato": stato,
                               "alternativo": (s[1] if p and s else None)}
        return scelta[1]

    # ── controllo interno sulle transazioni ──
    def controllo_acquisti(self, transazioni: list[dict], strumenti: dict) -> list[dict]:
        """Il prezzo di un acquisto/vendita deve cadere nel range della giornata (±tolleranza)."""
        esiti = []
        if not hasattr(self.principale, "intervallo"):
            return esiti
        for t in transazioni:
            if t["tipo"] not in ("acquisto", "vendita") or not t.get("prezzo") or t.get("prezzo_in_percento"):
                continue
            s = strumenti.get(t.get("strumento"))
            if not s or not s.get("ticker_mercato") or s.get("valutazione") != "mercato":
                continue
            rng = self.principale.intervallo(s["ticker_mercato"], t["data"])
            if rng is None:
                esiti.append({"strumento": s["chiave"], "data": t["data"], "stato": "non_verificabile"})
                continue
            lo, hi = rng
            ok = lo * (1 - TOLLERANZA_ACQUISTO) <= t["prezzo"] <= hi * (1 + TOLLERANZA_ACQUISTO)
            esiti.append({"strumento": s["chiave"], "nome": s.get("nome"), "data": t["data"], "prezzo_estratto": t["prezzo"],
                          "minimo": lo, "massimo": hi, "stato": "ok" if ok else "incoerente"})
        return esiti

    # ── rapporto per l'interfaccia ──
    def problemi(self) -> list[dict]:
        """Elenco di ciò che richiede una decisione umana prima di generare il report."""
        out = []
        for k, r in self.registro.items():
            if r["stato"] in ("discrepanza", "non_trovato", "ticker_mancante"):
                out.append({"tipo": "prezzo", "chiave": k, **r})
        for k, r in self.cambi_usati.items():
            if r["stato"] == "discrepanza":
                out.append({"tipo": "cambio", "chiave": k, **r})
        return out

    def snapshot_attuale(self) -> dict:
        snap = {k: dict(v) for k, v in self.registro.items() if v.get("prezzo") is not None}
        snap.update({k: {"tasso": v["tasso"], "fonte": v["fonte"]} for k, v in self.cambi_usati.items()})
        return snap


def mercato_reale(manuali: dict | None = None, snapshot: dict | None = None) -> Mercato:
    """Configurazione standard dell'app: Yahoo + Stooq per i titoli, BCE per i cambi, con cache su disco."""
    return Mercato(YahooFonte(), controllo_titoli=StooqFonte(), controllo_cambi=BceFonte(), cache=Cache(), manuali=manuali, snapshot=snapshot)
