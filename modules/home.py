import streamlit as st

from core import dati
from core.config import NOME_STUDIO
from core.nav import vai


def render():
    st.markdown("<p class='hero-etichetta'>REPORT FINANZIARI</p>", unsafe_allow_html=True)
    st.markdown(f"## {NOME_STUDIO}")
    st.caption("Report trimestrali, semestrali e annuali sugli investimenti dei clienti.")
    n = len(dati.elenco_clienti())
    r = len(dati.elenco_report())
    c1, c2 = st.columns(2)
    c1.metric("Clienti", n)
    c2.metric("Report archiviati", r)
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
