import streamlit as st

from core import dati, live
from core.config import CATEGORIE
from modules import strategia
from core.config import NOME_STUDIO
from core.nav import vai


def render():
    st.markdown("<p class='hero-etichetta'>REPORT FINANZIARI</p>", unsafe_allow_html=True)
    st.markdown(f"## {NOME_STUDIO}")
    st.caption("Report trimestrali, semestrali e annuali sugli investimenti dei clienti.")
    n = len(dati.elenco_clienti())
    r = len(dati.elenco_report())
    clienti = dati.elenco_clienti()
    ag = live.aggrega(clienti)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clienti", n)
    c2.metric("Report archiviati", r)
    c3.metric(f"Patrimonio gestito ({live.RIFERIMENTO})", f"{ag['valore']:,.0f}".replace(",", "’") if ag["valore"] else "–")
    c4.metric("Performance media (ogni cliente pesa uguale)", f"{100 * ag['perf_media']:+.2f}%" if ag["perf_media"] is not None else "–")
    ultimi = [pf["live"]["aggiornato"] for c in clienti for pf in c.get("portafogli", []) if (pf.get("live") or {}).get("aggiornato")]
    a, b = st.columns([4, 1], vertical_alignment="center")
    a.caption(("Dati aggiornati al " + min(ultimi)[:16].replace("T", " ") + ". ") if ultimi else "Nessun dato in diretta ancora: apri una strategia o premi «Aggiorna tutto».")
    if b.button("Aggiorna tutto", key="home_agg", width="stretch"):
        reg = dati.carica_registro()
        with st.spinner("Aggiorno prezzi e performance di tutti i portafogli…"):
            for c in clienti:
                for pf in c.get("portafogli", []):
                    live.aggiorna(c, pf, reg)
                dati.salva_cliente(c)
        st.rerun()
    if ag["senza_cambio"]:
        st.warning(f"{ag['senza_cambio']} portafogli non sono sommati perché manca il cambio in {live.RIFERIMENTO}: premi «Aggiorna tutto» quando i cambi sono disponibili.")
    if ag["allocazione"] or ag["serie"]:
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Allocazione totale**")
            strategia.torta(ag["allocazione"], CATEGORIE | {"liquidita": "Liquidità"})
        with g2:
            st.markdown("**Andamento della performance (media dei clienti)**")
            strategia.linea(ag["serie"])
    st.write("")
    voci = [("Clienti", "Archivio clienti, estratti conto e movimenti", "clienti"),
            ("Crea report", "Calcola la performance e genera il PDF", "report"),
            ("Archivio report", "Report già generati", "archivio_report"),
            ("Strumenti", "Anagrafica titoli, scadenze, barriere, ticker", "strumenti")]
    for i in range(0, len(voci), 2):
        cols = st.columns(2)
        for col, (t, d, v) in zip(cols, voci[i:i + 2]):
            with col, st.container(border=True):
                st.markdown(f"**{t}**")
                st.caption(d)
                if st.button("Apri", key=f"home_{v}", width="stretch"):
                    vai(v)
