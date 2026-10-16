"""Home: numeri in diretta, notizie sui prodotti dei clienti e sull'economia, tabella dei cambi e collegamenti rapidi. Nessun grafico."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import dati, live, notizie
from core.config import CATEGORIE, NOME_STUDIO
from core.nav import vai
from core.stile import bottone, bottone_link, riquadro

ETICHETTE = CATEGORIE | {"liquidita": "Liquidità", "deposito": "Depositi a termine"}

COLLEGAMENTI = [
    ("Leonteq · prodotti strutturati", "https://structuredproducts-ch.leonteq.com/", "blu"),
    ("ICTax · tassi di cambio", "https://www.ictax.admin.ch/extern/it.html#/ratelist/2025", "azzurro"),
    ("UBS Quotes", "https://quotes-global1.ubs.com/app/CGT/Workbench", "blu"),
    ("TradingView", "https://www.tradingview.com/symbols/NYSE-KO/", "azzurro"),
    ("Interactive Brokers", "https://www.interactivebrokers.co.uk/sso/Login?status=UNRE&deepLinkTo=/dashboard", "verde"),
    ("DEGIRO", "https://trader.degiro.nl/login/?redirectUrl=https%3A%2F%2Ftrader.degiro.nl%2Ftrader%2F%23%2Fportfolio%2Fassets#/login", "verde"),
    ("Swissquote", "https://swissquote.ch/trading-platform/#markets", "giallo"),
    ("PostFinance", "https://www.postfinance.ch/ap/ra/ob/html/finance/home?login", "giallo"),
]

INDICI = [("AMEX:URTH", "MSCI World (ETF iShares URTH)"), ("FOREXCOM:SPXUSD", "S&P 500"), ("FOREXCOM:NSXUSD", "Nasdaq 100"), ("TVC:SX5E", "Euro Stoxx 50"),
          ("INDEX:FTSEMIB", "FTSE MIB"), ("TVC:IBEX35", "IBEX 35"), ("XETR:DAX", "DAX"), ("TVC:CAC40", "CAC 40"), ("TVC:AEX", "AEX"), ("TVC:UKX", "FTSE 100")]


def _tape() -> str:
    simboli = ",".join('{"proName":"%s","title":"%s"}' % (k, t) for k, t in INDICI)
    return ('<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div>'
            '<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>'
            '{"symbols":[' + simboli + '],"showSymbolLogo":false,"colorTheme":"dark","isTransparent":true,"displayMode":"adaptive","locale":"it"}</script></div>')


def _quotes() -> str:
    simboli = ",".join('{"name":"%s","displayName":"%s"}' % (k, t) for k, t in INDICI)
    return ('<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div>'
            '<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js" async>'
            '{"width":"100%","height":470,"symbolsGroups":[{"name":"Indici azionari","symbols":[' + simboli + ']}],"showSymbolLogo":false,"colorTheme":"dark","isTransparent":true,"locale":"it"}'
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


@st.cache_data(ttl=900, show_spinner=False)
def _cambi():
    return notizie.tabella_cambi("CHF")


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


def render():
    st.markdown("<p class='hero-etichetta'>REPORT FINANZIARI</p>", unsafe_allow_html=True)
    st.markdown(f"## {NOME_STUDIO}")
    _html(_tape(), 74)
    clienti = dati.elenco_clienti()
    reg = dati.carica_registro()
    ag = live.aggrega(clienti)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clienti", len(clienti))
    c2.metric("Report archiviati", len(dati.elenco_report()))
    c3.metric(f"Patrimonio gestito ({live.RIFERIMENTO})", f"{ag['valore']:,.0f}".replace(",", "’") if ag["valore"] else "–")
    c4.metric("Performance media (ogni cliente pesa uguale)", f"{100 * ag['perf_media']:+.2f}%" if ag["perf_media"] is not None else "–")
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

    # ── allocazione totale (tabella, senza grafici) ──
    if ag["allocazione"]:
        with riquadro("verde", "home_alloc"):
            st.markdown("#### Allocazione totale di tutti i clienti")
            tot = sum(ag["allocazione"].values()) or 1.0
            st.dataframe(pd.DataFrame([{"Tipo": ETICHETTE.get(k, k), f"Valore ({live.RIFERIMENTO})": v, "Quota": v / tot} for k, v in sorted(ag["allocazione"].items(), key=lambda kv: -kv[1]) if v > 0]),
                         hide_index=True, width="stretch", column_config={f"Valore ({live.RIFERIMENTO})": st.column_config.NumberColumn(format="%.0f"),
                                                                           "Quota": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="percent")})

    # ── notizie e cambi ──
    simboli = _simboli_clienti(clienti, reg)
    g1, g2 = st.columns([3, 2])
    with g1, riquadro("blu", "home_news"):
        st.markdown("#### Notizie sui tuoi prodotti")
        news = _news_titoli(tuple(simboli)) if simboli else []
        if news:
            _elenco_news(news[:10])
        elif simboli:
            st.caption("Notizie non disponibili in questo momento (fonte non raggiungibile). Riprova fra poco.")
        else:
            st.caption("Le notizie compaiono quando i clienti hanno prodotti con ticker.")
    with g2, riquadro("azzurro", "home_fx"):
        st.markdown("#### Cambi principali (BCE)")
        fx = _cambi()
        if fx:
            st.dataframe(pd.DataFrame(fx).drop(columns=["Data"]), hide_index=True, width="stretch", column_config={
                "Variazione": st.column_config.NumberColumn(format="percent"), "Vale in CHF": st.column_config.NumberColumn(format="%.4f"), "1 CHF in valuta": st.column_config.NumberColumn(format="%.4f")})
            st.caption(f"Cambi BCE del {fx[0]['Data']}. Il valore indica quanti franchi vale una unità della valuta.")
        else:
            st.caption("Cambi non disponibili in questo momento.")
    with riquadro("blu", "home_indici"):
        st.markdown("#### Indici in diretta")
        _html(_quotes(), 480)
        st.caption("Quotazioni TradingView in tempo reale o con il ritardo previsto dalla borsa. MSCI World è rappresentato dall'ETF iShares URTH, che lo replica.")
    with riquadro("giallo", "home_macro"):
        st.markdown("#### Notizie economiche e di mercato")
        macro = _news_macro()
        if macro:
            _elenco_news(macro[:8])
        else:
            _html(_TIMELINE, 440)

    # ── collegamenti e accessi rapidi ──
    st.write("")
    k1, k2, k3 = st.columns(3)
    for col, (t, d, v, colore) in zip((k1, k2, k3), [("Clienti", "Strategie, estratti conto e movimenti", "clienti", "blu"), ("Crea report", "Performance e PDF per il cliente", "report", "verde"),
                                                  ("Archivio report", "Report già generati", "archivio_report", "giallo")]):
        with col, riquadro(colore, f"home_tile_{v}"):
            st.markdown(f"**{t}**")
            st.caption(d)
            if st.button("Apri", key=f"home_{v}", width="stretch"):
                vai(v)
    with riquadro("azzurro", "home_link"):
        st.markdown("#### Collegamenti rapidi")
        for i in range(0, len(COLLEGAMENTI), 4):
            cols = st.columns(4)
            for col, (et, url, colore) in zip(cols, COLLEGAMENTI[i:i + 4]):
                with col:
                    bottone_link(et, colore, f"lnk_{i}_{et[:6]}", url, width="stretch")
