"""Home: numeri in diretta, notizie sui prodotti dei clienti e sull'economia, tabella dei cambi e collegamenti rapidi. Nessun grafico."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import dati, live, notizie
from core.config import CATEGORIE, NOME_STUDIO
from core.nav import vai
from core.stile import bottone, bottone_link, num_ch, riquadro

ETICHETTE = CATEGORIE | {"liquidita": "Liquidità", "deposito": "Depositi a termine"}

COLLEGAMENTI = [
    ("Leonteq · prodotti strutturati", "https://structuredproducts-ch.leonteq.com/"),
    ("UBS Quotes", "https://quotes-global1.ubs.com/app/CGT/Workbench"),
    ("TradingView", "https://www.tradingview.com/symbols/NYSE-KO/"),
    ("Interactive Brokers", "https://www.interactivebrokers.co.uk/sso/Login?status=UNRE&deepLinkTo=/dashboard"),
    ("DEGIRO", "https://trader.degiro.nl/login/?redirectUrl=https%3A%2F%2Ftrader.degiro.nl%2Ftrader%2F%23%2Fportfolio%2Fassets#/login"),
    ("Swissquote", "https://swissquote.ch/trading-platform/#markets"),
    ("PostFinance", "https://www.postfinance.ch/ap/ra/ob/html/finance/home?login"),
]

INDICI = [("AMEX:URTH", "MSCI World (ETF iShares URTH)"), ("FOREXCOM:SPXUSD", "S&P 500"), ("FOREXCOM:NSXUSD", "Nasdaq 100"), ("TVC:SX5E", "Euro Stoxx 50"),
          ("INDEX:FTSEMIB", "FTSE MIB"), ("TVC:IBEX35", "IBEX 35"), ("XETR:DAX", "DAX"), ("TVC:CAC40", "CAC 40"), ("TVC:AEX", "AEX"), ("TVC:UKX", "FTSE 100")]


def _tape() -> str:
    simboli = ",".join('{"proName":"%s","title":"%s"}' % (k, t) for k, t in INDICI)
    return ('<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div>'
            '<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>'
            '{"symbols":[' + simboli + '],"showSymbolLogo":false,"colorTheme":"dark","isTransparent":true,"displayMode":"adaptive","locale":"it"}</script></div>')


CAMBI = [("FX_IDC:EURCHF", "EUR/CHF"), ("FX_IDC:USDCHF", "USD/CHF"), ("FX_IDC:GBPCHF", "GBP/CHF"), ("FX_IDC:JPYCHF", "JPY/CHF"), ("FX_IDC:CADCHF", "CAD/CHF"),
         ("FX_IDC:AUDCHF", "AUD/CHF"), ("FX_IDC:SEKCHF", "SEK/CHF"), ("FX_IDC:EURUSD", "EUR/USD"), ("FX_IDC:GBPUSD", "GBP/USD")]


def _quotes_cambi() -> str:
    simboli = ",".join('{"name":"%s","displayName":"%s"}' % (k, t) for k, t in CAMBI)
    return ('<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div>'
            '<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js" async>'
            '{"width":"100%","height":370,"symbolsGroups":[{"name":"Cambi principali","symbols":[' + simboli + ']}],"showSymbolLogo":false,"colorTheme":"dark","isTransparent":true,"locale":"it"}'
            '</script></div>')


_TIMELINE = """<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div>
<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-timeline.js" async>
{"feedMode":"market","market":"stock","isTransparent":true,"displayMode":"regular","width":"100%","height":"420","colorTheme":"dark","locale":"it"}
</script></div>"""


def _html(codice: str, altezza: int):
    """Incorpora un widget (TradingView). st.iframe nelle versioni recenti di Streamlit; components.html nelle precedenti."""
    if hasattr(st, "iframe"):
        st.iframe(codice, height=altezza)
    else:
        import streamlit.components.v1 as components
        components.html(codice, height=altezza)


@st.cache_data(ttl=600, show_spinner=False)
def _news_titoli(simboli: tuple):
    return notizie.notizie_portafogli(list(simboli))


@st.cache_data(ttl=900, show_spinner=False)
def _news_macro():
    return notizie.notizie_macro()


def _simboli_clienti(clienti, reg) -> list[tuple[str, str]]:
    """(etichetta, simbolo) dei prodotti con quotazione presenti nelle strategie dei clienti."""
    out, visti = [], set()
    for c in clienti:
        for t in c.get("transazioni", []):
            s = reg.strumenti.get(t.get("strumento"))
            if s and s.get("ticker_mercato") and s["ticker_mercato"] not in visti:
                visti.add(s["ticker_mercato"])
                out.append(((s.get("ticker") or s["ticker_mercato"]).upper(), s["ticker_mercato"]))
    return out


def _elenco_news(righe: list[dict]):
    for n in righe:
        quando = ""
        if n.get("data"):
            try:
                quando = pd.Timestamp(n["data"]).strftime("%d.%m %H:%M")
            except Exception:
                quando = ""
        st.markdown(f"<div style='margin:0 0 0.55rem 0'><span style='color:#7C9CFF;font-size:0.75rem;font-weight:650'>{n.get('etichetta', '')}</span> "
                    f"<span style='color:#9A9FAD;font-size:0.72rem'>{quando} {('· ' + n['fonte']) if n.get('fonte') else ''}</span><br/>"
                    f"<a href='{n['link']}' target='_blank' style='color:#F4EFE6;text-decoration:none'>{n['titolo']}</a></div>", unsafe_allow_html=True)


def _tabella_quota(valori: dict, etichette: dict, rif: str) -> str:
    tot = sum(v for v in valori.values() if v > 0) or 1.0
    righe = []
    for k, v in sorted(valori.items(), key=lambda kv: -kv[1]):
        if v <= 0:
            continue
        q = v / tot
        righe.append(f"<tr><td>{etichette.get(k, k)}</td><td><div class='barra-quota'><div class='pista'><div class='riemp' style='width:{100 * q:.1f}%'></div></div>"
                     f"<span style='min-width:3.2rem;text-align:right'>{num_ch(100 * q, 1)}%</span></div></td><td class='num'>{num_ch(v, 2)}</td></tr>")
    return f"<table class='tab-quota'><tr><th>Tipo</th><th>Quota</th><th style='text-align:right'>Valore ({rif})</th></tr>{''.join(righe)}</table>"


def render():
    st.markdown("<p class='hero-etichetta'>REPORT FINANZIARI</p>", unsafe_allow_html=True)
    st.markdown(f"## {NOME_STUDIO}")
    _html(_tape(), 74)
    clienti = dati.elenco_clienti()
    reg = dati.carica_registro()
    ag = live.aggrega(clienti)

    # ── allocazione totale (sotto gli indici che scorrono) ──
    if ag["allocazione"]:
        with riquadro("verdescuro", "home_alloc"):
            st.markdown("#### Allocazione totale di tutti i clienti")
            st.markdown(_tabella_quota(ag["allocazione"], ETICHETTE, live.RIFERIMENTO), unsafe_allow_html=True)

    # ── numeri ──
    c1, c2, c3 = st.columns(3)
    c1.metric("Clienti", len(clienti))
    c2.metric("Report archiviati", len(dati.elenco_report()))
    c3.metric(f"Patrimonio gestito ({live.RIFERIMENTO})", num_ch(ag["valore"], 2) if ag["valore"] else "–")
    ultimi = [pf["live"]["aggiornato"] for c in clienti for pf in c.get("portafogli", []) if (pf.get("live") or {}).get("aggiornato")]
    a, b = st.columns([4, 1], vertical_alignment="center")
    a.caption(("Dati aggiornati al " + min(ultimi)[:16].replace("T", " ") + ". ") if ultimi else "Nessun dato in diretta ancora: apri una strategia o premi «Aggiorna tutto».")
    if b.button("Aggiorna tutto", key="home_agg", width="stretch"):
        with st.spinner("Aggiorno prezzi e performance di tutti i portafogli…"):
            for c in clienti:
                for pf in c.get("portafogli", []):
                    live.aggiorna(c, pf, reg)
                dati.salva_cliente(c)
        st.rerun()
    if ag["senza_cambio"]:
        st.warning(f"{ag['senza_cambio']} portafogli non sono sommati perché manca il cambio in {live.RIFERIMENTO}: premi «Aggiorna tutto» quando i cambi sono disponibili.")

    # ── accessi rapidi (sotto i numeri) ──
    k1, k2, k3 = st.columns(3)
    for col, (t, v) in zip((k1, k2, k3), [("Clienti", "clienti"), ("Crea report", "report"), ("Archivio report", "archivio_report")]):
        with col:
            if bottone(t, "bianco", f"home_{v}", width="stretch"):
                vai(v)

    # ── notizie: stessa linea, stessa altezza, bordo blu ──
    simboli = _simboli_clienti(clienti, reg)
    g1, g2 = st.columns(2)
    with g1, riquadro("blu", "home_news", 470):
        st.markdown("#### Notizie sui tuoi prodotti")
        news = _news_titoli(tuple(simboli)) if simboli else []
        if news:
            _elenco_news(news[:12])
        elif simboli:
            st.caption("Notizie non disponibili in questo momento (fonte non raggiungibile). Riprova fra poco.")
        else:
            st.caption("Le notizie compaiono quando i clienti hanno prodotti con ticker.")
    with g2, riquadro("blu", "home_macro", 470):
        st.markdown("#### Notizie economiche e di mercato")
        macro = _news_macro()
        if macro:
            _elenco_news(macro[:12])
        else:
            _html(_TIMELINE, 400)

    # ── cambi in tempo reale e collegamenti rapidi, nella stessa forma ──
    f1, f2 = st.columns(2)
    with f1, riquadro("blu", "home_fx", 470):
        st.markdown("#### Cambi principali")
        _html(_quotes_cambi(), 380)
    with f2, riquadro("blu", "home_link", 470):
        st.markdown("#### Collegamenti rapidi")
        for i in range(0, len(COLLEGAMENTI), 2):
            cols = st.columns(2)
            for col, (et, url) in zip(cols, COLLEGAMENTI[i:i + 2]):
                with col:
                    bottone_link(et, "blubianco", f"lnk_{i}_{et[:6]}", url, width="stretch")
