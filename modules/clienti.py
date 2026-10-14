import streamlit as st

from core import dati
from core.config import VALUTE_BASE
from core.nav import vai
from core.stile import intestazione


def render():
    intestazione("Clienti", "Archivio dei clienti con le loro posizioni.")
    with st.expander("Nuovo cliente"):
        with st.form("nuovo_cliente", clear_on_submit=True):
            nome = st.text_input("Nome e cognome / ragione sociale")
            c1, c2 = st.columns(2)
            valuta = c1.selectbox("Valuta di riferimento", VALUTE_BASE)
            rischio = c2.selectbox("Profilo di rischio (1 basso – 5 alto)", [1, 2, 3, 4, 5], index=1)
            note = st.text_area("Note")
            if st.form_submit_button("Crea cliente", type="primary") and nome.strip():
                c = dati.nuovo_cliente(nome, valuta, rischio, note)
                vai("cliente", cli_id=c["id"])
    elenco = dati.elenco_clienti()
    if not elenco:
        st.info("Nessun cliente. Creane uno qui sopra.")
        return
    for c in elenco:
        with st.container(border=True):
            a, b = st.columns([4, 1], vertical_alignment="center")
            a.markdown(f"**{c['nome']}**  \n<span style='color:#9A9AA2'>{c['valuta_base']} · rischio {c.get('rischio', '-')} · {len(c.get('transazioni', []))} movimenti</span>", unsafe_allow_html=True)
            if b.button("Apri", key=f"ap_{c['id']}", width="stretch"):
                vai("cliente", cli_id=c["id"])
