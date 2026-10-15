import streamlit as st

from core import dati
from core.config import CATEGORIE, SOTTOCATEGORIE_ALTERNATIVI, SOTTOCATEGORIE_STRUTTURATI, VALUTAZIONI
from core.stile import intestazione


def render():
    intestazione("Strumenti", "Anagrafica comune a tutti i clienti. Controlla gli strumenti nuovi: ticker, scadenza, barriera.")
    reg = dati.carica_registro()
    if not reg.strumenti:
        st.info("Nessuno strumento: si creano da soli importando un estratto conto.")
        return
    solo = st.checkbox("Mostra solo da verificare", value=True, key="str_solo")
    for k, s in sorted(reg.strumenti.items(), key=lambda x: x[1].get("nome", "")):
        if solo and s.get("confermato"):
            continue
        stato = "✓" if s.get("confermato") else "da verificare"
        with st.expander(f"{s.get('nome') or k} — {CATEGORIE.get(s['categoria'], '')} · {stato}"):
            from modules import scheda_prodotto as sp
            sp.scheda(reg, k)
