from datetime import date

import pandas as pd
import streamlit as st

from core import dati
from core.config import PERIODI
from core.mercato import mercato_reale
from core.performance import Contesto, DatoMancante, calcola
from core.report_pdf import genera_pdf
from core.stile import intestazione


def _da(a: date, mesi: int) -> date:
    return (pd.Timestamp(a) - pd.DateOffset(months=mesi)).date()


def _calcola(c, reg, tipo, da, a):
    manuali = dati.carica_manuali()
    m = mercato_reale(manuali=manuali)
    ctx = Contesto(base=c["valuta_base"], fx=m.fx, prezzo=m.prezzo, spot=m.spot)
    tx = dati.transazioni_ordinate(c)
    ris = calcola(tx, reg.strumenti, str(da), str(a), ctx, saldi_liquidita=dati.saldi_a_data(c, str(a)))
    incoerenti = [e for e in m.controllo_acquisti(tx, reg.strumenti) if e["stato"] == "incoerente"]
    return {"ris": ris, "problemi": m.problemi(), "incoerenti": incoerenti, "snapshot": m.snapshot_attuale(),
            "tipo": tipo, "da": str(da), "a": str(a), "cliente": c["id"]}


def render():
    intestazione("Crea report", "Scegli cliente e periodo: i prezzi di mercato vengono controllati su due fonti.")
    clienti = dati.elenco_clienti()
    if not clienti:
        st.info("Crea prima un cliente.")
        return
    reg = dati.carica_registro()
    ids = [c["id"] for c in clienti]
    pre = st.session_state.get("cli_id")
    c_id = st.selectbox("Cliente", ids, index=ids.index(pre) if pre in ids else 0, format_func=lambda i: next(c["nome"] for c in clienti if c["id"] == i), key="rep_cliente")
    c = dati.carica_cliente(c_id)
    col1, col2 = st.columns(2)
    tipo = col1.selectbox("Tipo di report", list(PERIODI), key="rep_tipo")
    a = col2.date_input("Fino al (data di fine periodo)", value=date.today(), key="rep_a")
    da = _da(a, PERIODI[tipo])
    st.caption(f"Periodo: {da.strftime('%d.%m.%Y')} → {a.strftime('%d.%m.%Y')}")
    if not c.get("transazioni"):
        st.warning("Il cliente non ha ancora movimenti: importa un estratto conto o inserisci le posizioni iniziali.")
        return
    nonconf = [s["nome"] for s in reg.strumenti.values() if not s.get("confermato")]
    if nonconf:
        st.info(f"{len(nonconf)} strumenti non ancora verificati in «Strumenti» (ticker, scadenza, barriera): il report è possibile ma può risultare incompleto.")

    if st.button("Calcola", type="primary", key="rep_calcola"):
        with st.spinner("Recupero prezzi e cambi, doppio controllo…"):
            try:
                st.session_state["rep_stato"] = _calcola(c, reg, tipo, da, a)
            except DatoMancante as e:
                st.session_state.pop("rep_stato", None)
                st.error(f"Dato mancante: {e}. Inserisci il valore a mano qui sotto o correggi lo strumento.")
    S = st.session_state.get("rep_stato")
    if not S or S["cliente"] != c_id:
        return

    ris = S["ris"]
    bloccanti = S["problemi"] or S["incoerenti"]
    if S["problemi"]:
        st.markdown("### Prezzi e cambi da verificare")
        manuali = dati.carica_manuali()
        for p in S["problemi"]:
            with st.container(border=True):
                if p["tipo"] == "prezzo":
                    st.markdown(f"**{p['chiave']}** — {p['stato'].replace('_', ' ')}")
                    if p.get("prezzo") is not None:
                        st.caption(f"{p.get('fonte', '')}: {p['prezzo']}  ·  controllo {p.get('fonte_controllo', '')}: {p.get('prezzo_controllo')}  ·  scarto {p.get('scarto', 0):.2%}")
                else:
                    st.markdown(f"**Cambio {p['chiave']}** — discrepanza tra fonti ({p['tasso']} vs {p.get('alternativo')})")
                v = st.number_input("Valore da usare", value=float(p.get("prezzo") or p.get("tasso") or 0.0), format="%.6f", key=f"rep_man_{p['chiave']}")
                if st.button("Conferma questo valore", key=f"rep_ok_{p['chiave']}"):
                    manuali[p["chiave"]] = v
                    dati.salva_manuali(manuali)
                    st.session_state["rep_stato"] = _calcola(c, reg, S["tipo"], date.fromisoformat(S["da"]), date.fromisoformat(S["a"]))
                    st.rerun()
    if S["incoerenti"]:
        st.markdown("### Acquisti incoerenti con il mercato")
        st.caption("Il prezzo dell'estratto cade fuori dal range della giornata: controlla ticker, valuta o l'estratto.")
        st.dataframe(pd.DataFrame(S["incoerenti"]), hide_index=True, width="stretch")
        if st.checkbox("Ho verificato: procedi comunque", key="rep_forza"):
            bloccanti = S["problemi"]

    t = ris["totale"]
    st.markdown("### Anteprima")
    k = st.columns(3)
    k[0].metric("Valore finale", f"{t.get('v1', 0):,.0f}".replace(",", "’") if isinstance(t.get("v1"), (int, float)) else "—")
    for av in ris.get("avvisi", []):
        st.warning(av)
    commento = st.text_area("Commento (facoltativo)", key="rep_commento", height=140)
    if st.button("Genera PDF", type="primary", disabled=bool(bloccanti), key="rep_genera"):
        pdf = genera_pdf(ris, c, S["tipo"], commento)
        meta = dati.salva_report({"cliente_id": c["id"], "cliente": c["nome"], "tipo": S["tipo"], "da": S["da"], "a": S["a"],
                                  "commento": commento, "snapshot": S["snapshot"]}, pdf)
        st.session_state["rep_pdf"] = (pdf, f"Report_{c['nome'].replace(' ', '_')}_{S['a']}.pdf")
        st.success("Report generato e archiviato.")
    if st.session_state.get("rep_pdf"):
        pdf, nome = st.session_state["rep_pdf"]
        st.download_button("Scarica PDF", pdf, file_name=nome, mime="application/pdf")
    if bloccanti:
        st.caption("La generazione è bloccata finché i punti sopra non sono risolti.")
