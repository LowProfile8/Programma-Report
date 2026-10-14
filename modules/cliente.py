import pandas as pd
import streamlit as st

from core import dati
from core.config import VALUTE_BASE
from core.nav import vai
from core.importatore import leggi_documento
from core.stile import intestazione

VALUTE = ["CHF", "EUR", "USD", "GBP", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"]


def _anteprima_movimenti(nome, est):
    with st.container(border=True):
        st.markdown(f"**{nome}** — {est.banca}, movimenti dal {est.periodo_da} al {est.periodo_a}: {len(est.movimenti)} righe")
        if est.quadra:
            st.success("Controlli di quadratura superati: i saldi tornano.")
        else:
            st.error("I saldi NON quadrano con i movimenti letti. Controlla il PDF prima di importare.")
        for k in est.controlli:
            if not k.get("ok", True):
                st.write(f"- {k['testo']}")
        for a in est.avvisi:
            st.warning(a)


def _anteprima_posizioni(nome, doc):
    with st.container(border=True):
        st.markdown(f"**{nome}** — {doc['banca']}, posizioni al {doc['data']} ({doc['valuta_base']}): {len(doc['posizioni'])} strumenti, {len(doc['liquidita'])} conti")
        for k in doc["controlli"]:
            (st.success if k["ok"] else st.error)(k["testo"])
        for a in doc["avvisi"]:
            st.warning(a)
        righe = [{"Strumento": p["nome"], "ISIN": p.get("isin", ""), "Valuta": p["valuta"], "Quantità": p["quantita"],
                  "Prezzo acquisto %": p.get("prezzo_acquisto_pct"), "Data acquisto": p.get("data_acquisto") or "(alla data del documento)",
                  "Scadenza": p.get("scadenza", "")} for p in doc["posizioni"]]
        st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")
        st.caption("Le posizioni vengono registrate al prezzo d'acquisto indicato dal documento: servono come valore e quantità di partenza. "
                   "Non caricare anche gli estratti conto che contengono gli stessi acquisti, altrimenti si contano due volte.")
        d = doc.get("banca_dichiara") or {}
        if d.get("performance_pct") is not None:
            st.caption(f"Performance dichiarata dalla banca ({d.get('metodo', '')}): {d['performance_pct']:+.2f}% — utile per confrontarla con il report.")


def _estratti(c, reg):
    st.caption("Carica i PDF: estratti conto (PostFinance, Swissquote, UBS), «Performance del portafoglio» PostFinance/Swissquote o «Estratto patrimoniale» UBS. "
               "Il tipo di documento viene riconosciuto da solo.")
    files = st.file_uploader("Documenti (PDF)", type="pdf", accept_multiple_files=True, key="cli_upload")
    letti = []
    for f in files or []:
        try:
            tipo, doc = leggi_documento(f)
        except Exception as e:
            st.error(f"{f.name}: {e}")
            continue
        letti.append((f.name, tipo, doc))
        (_anteprima_movimenti if tipo == "movimenti" else _anteprima_posizioni)(f.name, doc)
    if letti and st.button("Importa nel cliente", type="primary", key="cli_importa"):
        tot_n = tot_d = 0
        avvisi = []
        for nome, tipo, doc in letti:
            r = dati.importa_estratto(c, doc.a_dict(), reg) if tipo == "movimenti" else dati.importa_posizioni(c, doc, reg)
            tot_n += r["nuovi"]; tot_d += r["duplicati"]; avvisi += r.get("avvisi", [])
        dati.salva_cliente(c)
        dati.salva_registro(reg)
        st.session_state.pop("cli_upload", None)
        st.success(f"Importati {tot_n} elementi nuovi ({tot_d} già presenti, ignorati). Controlla gli strumenti nuovi in «Strumenti».")
        for a in avvisi:
            st.warning(a)
    if c.get("estratti"):
        st.markdown("**Documenti già importati**")
        st.dataframe(pd.DataFrame(c["estratti"]), hide_index=True, width="stretch")


def _movimenti(c, reg):
    tx = dati.transazioni_ordinate(c)
    if tx:
        righe = [{"Data": t["data"], "Tipo": dati.ETICHETTE_TIPO.get(t["tipo"], t["tipo"]),
                  "Strumento": (reg.strumenti.get(t.get("strumento")) or {}).get("nome") or t.get("titolo", ""),
                  "Quantità": t.get("quantita"), "Valuta": t["valuta"], "Importo": t.get("importo_cassa")} for t in tx]
        st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")
    else:
        st.info("Nessun movimento.")
    with st.expander("Aggiungi movimento a mano (anche valori iniziali)"):
        st.caption("Per partire da una posizione già esistente, registra un acquisto alla data di apertura con quantità e importo.")
        with st.form("mov_manuale", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data = c1.date_input("Data")
            tipo = c2.selectbox("Tipo", list(dati.ETICHETTE_TIPO), format_func=lambda k: dati.ETICHETTE_TIPO[k])
            chiavi = [""] + sorted(reg.strumenti, key=lambda k: reg.strumenti[k].get("nome", ""))
            strum = st.selectbox("Strumento", chiavi, format_func=lambda k: reg.strumenti[k]["nome"] if k else "—")
            c3, c4, c5 = st.columns(3)
            valuta = c3.selectbox("Valuta", VALUTE)
            qta = c4.number_input("Quantità / nominale", value=0.0, format="%.4f")
            importo = c5.number_input("Importo in cassa (− esce, + entra)", value=0.0, format="%.2f")
            titolo = st.text_input("Descrizione")
            if st.form_submit_button("Aggiungi", type="primary"):
                dati.aggiungi_movimento_manuale(c, data=str(data), tipo=tipo, valuta=valuta, importo_cassa=importo,
                                                quantita=qta or None, strumento=strum, titolo=titolo)
                dati.salva_cliente(c)
                st.rerun()


def _deposito(c, reg):
    with st.expander("Deposito a termine / vincolato (da lettera della banca)"):
        st.caption("Per documenti in forma di scansione (es. Raiffeisen «Deposito vincolato – Rimborso»): inserisci i dati della lettera.")
        with st.form("dep_termine", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            banca = c1.text_input("Banca", "Raiffeisen")
            numero = c2.text_input("Numero prodotto")
            valuta = c3.selectbox("Valuta", VALUTE, key="dep_val")
            d1, d2, d3 = st.columns(3)
            nominale = d1.number_input("Nominale", min_value=0.0, value=0.0, format="%.2f")
            tasso = d2.number_input("Tasso % p.a.", value=0.0, format="%.4f")
            inizio = d3.date_input("Inizio", key="dep_ini")
            e1, e2, e3 = st.columns(3)
            fine = e1.date_input("Scadenza / rimborso", key="dep_fin")
            lordo = e2.number_input("Interesse lordo", value=0.0, format="%.2f")
            imposta = e3.number_input("Imposta preventiva", value=0.0, format="%.2f")
            if st.form_submit_button("Registra deposito", type="primary") and nominale > 0:
                dati.aggiungi_deposito_termine(c, reg, banca, numero or "n/d", valuta, nominale, tasso, str(inizio), str(fine), lordo, imposta)
                dati.salva_cliente(c)
                dati.salva_registro(reg)
                st.success("Deposito registrato (acquisto, interesse, imposta, rimborso).")


def _dati(c):
    with st.form("dati_cliente"):
        nome = st.text_input("Nome", c["nome"])
        c1, c2 = st.columns(2)
        valuta = c1.selectbox("Valuta di riferimento", VALUTE_BASE, index=VALUTE_BASE.index(c["valuta_base"]) if c["valuta_base"] in VALUTE_BASE else 0)
        rischio = c2.selectbox("Rischio", [1, 2, 3, 4, 5], index=int(c.get("rischio", 2)) - 1)
        note = st.text_area("Note", c.get("note", ""))
        if st.form_submit_button("Salva", type="primary"):
            c.update(nome=nome.strip() or c["nome"], valuta_base=valuta, rischio=rischio, note=note)
            dati.salva_cliente(c)
            st.success("Salvato.")
    with st.expander("Elimina cliente"):
        conf = st.checkbox("Confermo: eliminare il cliente e tutti i suoi movimenti", key="cli_conf_elim")
        if st.button("Elimina definitivamente", disabled=not conf):
            dati.elimina_cliente(c["id"])
            st.session_state.pop("cli_id", None)
            vai("clienti")


def render():
    c = dati.carica_cliente(st.session_state.get("cli_id", "")) if st.session_state.get("cli_id") else None
    if not c:
        vai("clienti")
        return
    intestazione(c["nome"], f"{c['valuta_base']} · rischio {c.get('rischio', '-')}")
    reg = dati.carica_registro()
    t1, t2, t3 = st.tabs(["Estratti conto", "Movimenti", "Dati cliente"])
    with t1:
        _estratti(c, reg)
    with t2:
        _movimenti(c, reg)
        _deposito(c, reg)
    with t3:
        _dati(c)
