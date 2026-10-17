import streamlit as st

from core import dati
from core.stile import bottone, gma, intestazione, riquadro


def render():
    intestazione("Archivio report", "Report già generati: i prezzi usati sono congelati.")
    elenco = dati.elenco_report()
    if not elenco:
        st.info("Nessun report archiviato.")
        return
    for r in elenco:
        with riquadro("bianco", f"arc_{r['id']}"):
            a, b, c = st.columns([6, 1, 1], vertical_alignment="center")
            a.markdown(f"**{r['cliente']}** — {r['tipo']}  \n<span style='color:#9A9AA2'>{gma(r['da'])} → {gma(r['a'])} · creato {gma(r['creato'][:10])} {r['creato'][11:16]}</span>", unsafe_allow_html=True)
            with b:                                       # il PDF si scarica dal cloud solo quando clicchi, non a ogni apertura della pagina
                st.download_button("PDF", (lambda i=r["id"]: dati.pdf_report(i) or b""), file_name=f"Report_{r['cliente'].replace(' ', '_')}_{r['a']}.pdf", mime="application/pdf",
                                   key=f"dl_{r['id']}", on_click="ignore", width="stretch", icon=":material/download:")
            with c:
                if bottone("Elimina", "giallo", f"del_{r['id']}", width="stretch"):
                    dati.elimina_report(r["id"])
                    st.rerun()
