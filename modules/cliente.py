import pandas as pd
import streamlit as st

from core import dati
from core.config import VALUTE_BASE
from core.nav import vai
from core.importatore import leggi_documento
from core.stile import intestazione

VALUTE = ["CHF", "EUR", "USD", "GBP", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"]


def _stato_prodotto(c, k):
    tx = [t for t in c["transazioni"] if t.get("strumento") == k]
    qta = sum((t.get("quantita") or 0) * (1 if t["tipo"] == "acquisto" else -1) for t in tx if t["tipo"] in ("acquisto", "vendita", "rimborso"))
    return "attivo" if qta > 1e-9 else "chiuso"


def _prodotti(c, reg):
    from core.completezza import problemi_strumento, prodotti_del_cliente
    from modules import scheda_prodotto as sp
    st.caption("Le condizioni di ogni prodotto (scadenza, cedola, barriera, sottostanti) si inseriscono qui, una volta. "
               "Poi il programma legge solo i dati reali: estratti conto o movimenti.")
    prod = prodotti_del_cliente(c, reg)
    if not prod:
        st.info("Nessun prodotto. Aggiungine uno a mano qui sotto, oppure carica un estratto conto in «Estratti conto».")
    for k, s in sorted(prod.items(), key=lambda x: (_stato_prodotto(c, x[0]), x[1].get("nome", ""))):
        pr = problemi_strumento(s)
        bl = sum(1 for g, _ in pr if g == "bloccante")
        badge = "🔴 da completare" if bl else ("🟡 da rivedere" if pr else "✓ completo")
        with st.expander(f"{s.get('nome') or k} · {_stato_prodotto(c, k)} · {badge}", expanded=bool(bl) and len(prod) <= 3):
            sp.scheda(reg, k, c)
    with st.expander("➕ Aggiungi prodotto a mano"):
        _nuovo_prodotto(c, reg)


def _nuovo_prodotto(c, reg):
    from core import anagrafica
    from core.config import CATEGORIE
    from modules import scheda_prodotto as sp
    st.caption("1) Condizioni del prodotto · 2) acquisto (data, quantità, prezzo, commissioni). L'importo addebitato viene calcolato e mostrato per il controllo.")
    with st.form("cli_nuovo_prod"):
        v = sp.campi_prodotto("np", {"valuta": c["valuta_base"], "categoria": "azione"})
        st.markdown("**Acquisto**")
        a1, a2, a3, a4 = st.columns(4)
        data = a1.date_input("Data acquisto", format="DD.MM.YYYY", key="np_data")
        qta = a2.number_input("Quantità / nominale", min_value=0.0, value=0.0, format="%.4f", key="np_q")
        prezzo = a3.number_input("Prezzo (in % se obbligazione/strutturato)", min_value=0.0, value=0.0, format="%.4f", key="np_p")
        comm = a4.number_input("Commissioni + tasse", min_value=0.0, value=0.0, format="%.2f", key="np_c")
        lordo = qta * prezzo / (100 if v["prezzo_in_percento"] else 1)
        st.info(f"Importo addebitato calcolato: **{lordo + comm:,.2f} {v['valuta']}**".replace(",", "’"))
        if st.form_submit_button("Aggiungi prodotto e acquisto", type="primary"):
            nome, isin = v["nome"], v["isin"]
            if not nome.strip() or qta <= 0 or prezzo <= 0:
                st.error("Servono nome, quantità e prezzo.")
            else:
                v["nome"] = nome
                k = reg.assicura(isin, "" if isin else "MAN" + db_id(), nome.strip(), v["valuta"], v["prezzo_in_percento"])
                s = reg.strumenti[k]
                sp.applica_campi(s, v)
                if isin:
                    s["isin"] = isin
                dati.aggiungi_movimento_manuale(c, data=str(data), tipo="acquisto", valuta=v["valuta"], importo_cassa=-(lordo + comm), quantita=qta,
                                                prezzo=prezzo, prezzo_in_percento=v["prezzo_in_percento"], importo_lordo=lordo, commissione=comm,
                                                strumento=k, titolo=f"Acquisto {nome.strip()}")
                dati.salva_cliente(c)
                dati.salva_registro(reg)
                st.success("Prodotto e acquisto registrati.")
                st.rerun()


def db_id():
    from core import db
    return db.nuovo_id()[:8].upper()


def _revisione_movimenti(nome, est, c, reg):
    from core import revisione
    d = est.a_dict()
    st.markdown(f"**{nome}** · {est.banca} · dal {est.periodo_da} al {est.periodo_a} · {len(est.movimenti)} righe")
    (st.success if est.quadra else st.error)("Saldi quadrati con i movimenti." if est.quadra else "I saldi NON quadrano: controlla bene prima di importare.")
    for a in est.avvisi:
        st.warning(a)
    righe = revisione.prepara_revisione(d, c, reg)
    tipi = list(dati.ETICHETTE_TIPO)
    ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key=f"cli_rev_{nome}",
                        disabled=["Controllo", "Dettaglio", "ISIN", "Prodotto", "Valuta"],
                        column_config={"_i": None, "Tipo": st.column_config.SelectboxColumn(options=tipi, required=True),
                                       "Controllo": st.column_config.TextColumn(width="small"), "Dettaglio": st.column_config.TextColumn(width="large")})
    n_ko = sum(1 for r in righe if r["Controllo"] == "⚠" and r["Importa"])
    if n_ko:
        st.warning(f"{n_ko} operazioni con ⚠: quantità × prezzo + commissioni non torna con l'importo. Correggi nella tabella o togli la spunta.")
    return nome, d, ed.to_dict("records")


def _revisione_posizioni(nome, doc):
    from core import revisione
    st.markdown(f"**{nome}** · {doc['banca']} · posizioni al {doc['data']} · {len(doc['posizioni'])} strumenti")
    for k in doc["controlli"]:
        (st.success if k["ok"] else st.error)(k["testo"])
    for a in doc["avvisi"]:
        st.warning(a)
    ed = st.data_editor(pd.DataFrame(revisione.prepara_revisione_posizioni(doc)), hide_index=True, width="stretch", key=f"cli_revp_{nome}",
                        disabled=["Prodotto", "ISIN", "Valuta"], column_config={"_i": None})
    st.caption("Qui verifica quantità, prezzo d'acquisto e data per ogni prodotto: sono i valori di partenza del report. "
               "Non importare anche gli estratti conto con gli stessi acquisti.")
    return nome, doc, ed.to_dict("records")


def _estratti(c, reg):
    st.caption("Carica i PDF (estratti conto PostFinance, Swissquote, UBS; «Performance del portafoglio»; «Estratto patrimoniale» UBS). "
               "Vedrai ogni riga in una tabella modificabile con il controllo ✓/⚠. **Nulla viene salvato finché non confermi.**")
    files = st.file_uploader("Documenti (PDF)", type="pdf", accept_multiple_files=True, key="cli_upload")
    pronti = []
    for f in files or []:
        try:
            tipo, doc = leggi_documento(f)
        except Exception as e:
            st.error(f"{f.name}: {e}")
            continue
        with st.container(border=True):
            pronti.append((tipo,) + (_revisione_movimenti(f.name, doc, c, reg) if tipo == "movimenti" else _revisione_posizioni(f.name, doc)))
    if pronti and st.button("Conferma e importa le righe selezionate", type="primary", key="cli_importa"):
        from core import revisione
        n = d = 0
        avvisi, prima = [], set(reg.strumenti)
        for tipo, nome, doc, righe in pronti:
            if tipo == "movimenti":
                r = dati.importa_estratto(c, revisione.applica_modifiche(doc, righe), reg)
            else:
                r = dati.importa_posizioni(c, revisione.applica_modifiche_posizioni(doc, righe), reg)
            n += r["nuovi"]; d += r["duplicati"]; avvisi += r.get("avvisi", [])
        dati.salva_cliente(c)
        dati.salva_registro(reg)
        for k in ("cli_upload",):
            st.session_state.pop(k, None)
        nuovi = sorted(set(reg.strumenti) - prima)
        st.session_state["cli_msg"] = (f"Importati {n} elementi ({d} già presenti). " + (f"{len(nuovi)} prodotti nuovi: completa le condizioni in «Prodotti»." if nuovi else ""), avvisi)
        st.rerun()
    if c.get("estratti"):
        st.markdown("**Documenti già importati**")
        st.dataframe(pd.DataFrame(c["estratti"]), hide_index=True, width="stretch")


def _movimenti(c, reg):
    tx = dati.transazioni_ordinate(c)
    if tx:
        righe = [{"id": t["id"], "Elimina": False, "Data": t["data"], "Tipo": dati.ETICHETTE_TIPO.get(t["tipo"], t["tipo"]),
                  "Strumento": (reg.strumenti.get(t.get("strumento")) or {}).get("nome") or t.get("titolo", ""),
                  "Quantità": t.get("quantita"), "Prezzo": t.get("prezzo"), "Valuta": t["valuta"], "Importo": t.get("importo_cassa"), "Origine": t.get("fonte", "")} for t in tx]
        ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key="cli_mov_ed", column_config={"id": None},
                            disabled=["Tipo", "Strumento", "Valuta", "Origine"])
        if st.button("Salva modifiche ai movimenti", key="cli_mov_salva"):
            per_id = {t["id"]: t for t in c["transazioni"]}
            el = 0
            for r in ed.to_dict("records"):
                t = per_id[r["id"]]
                if r["Elimina"]:
                    c["transazioni"].remove(t); el += 1; continue
                t["data"] = str(r["Data"])
                t["quantita"] = r["Quantità"] if r["Quantità"] == r["Quantità"] else None
                t["prezzo"] = r["Prezzo"] if r["Prezzo"] == r["Prezzo"] else None
                t["importo_cassa"] = float(r["Importo"])
            dati.salva_cliente(c)
            st.success(f"Salvato ({el} eliminati)." if el else "Salvato.")
            st.rerun()
    else:
        st.info("Nessun movimento.")
    with st.expander("Aggiungi movimento a mano"):
        st.caption("Per un nuovo prodotto usa «Prodotti → Aggiungi prodotto». Qui: altri acquisti/vendite di prodotti già presenti, cedole, dividendi, costi, depositi.")
        c1, c2 = st.columns(2)
        data = c1.date_input("Data", format="DD.MM.YYYY", key="mm_data")
        tipo = c2.selectbox("Tipo", list(dati.ETICHETTE_TIPO), format_func=lambda k: dati.ETICHETTE_TIPO[k], key="mm_tipo")
        chiavi = [""] + sorted(reg.strumenti, key=lambda k: reg.strumenti[k].get("nome", ""))
        strum = st.selectbox("Strumento", chiavi, format_func=lambda k: reg.strumenti[k]["nome"] if k else "—", key="mm_str")
        s = reg.strumenti.get(strum) or {}
        c3, c4, c5, c6 = st.columns(4)
        valuta = c3.selectbox("Valuta", VALUTE, index=VALUTE.index(s["valuta"]) if s.get("valuta") in VALUTE else 0, key="mm_val")
        qta = c4.number_input("Quantità / nominale", value=0.0, format="%.4f", key="mm_q")
        prezzo = c5.number_input("Prezzo", value=0.0, format="%.4f", key="mm_p")
        comm = c6.number_input("Commissioni + tasse", min_value=0.0, value=0.0, format="%.2f", key="mm_c")
        pct = bool(s.get("prezzo_in_percento"))
        if tipo in ("acquisto", "vendita") and qta and prezzo:
            lordo = qta * prezzo / (100 if pct else 1)
            importo = -(lordo + comm) if tipo == "acquisto" else lordo - comm
            st.info(f"Importo calcolato: **{importo:+,.2f} {valuta}**".replace(",", "’"))
        else:
            lordo = None
            importo = st.number_input("Importo in cassa (− esce, + entra)", value=0.0, format="%.2f", key="mm_imp")
        titolo = st.text_input("Descrizione", key="mm_tit")
        if st.button("Aggiungi movimento", type="primary", key="mm_add"):
            dati.aggiungi_movimento_manuale(c, data=str(data), tipo=tipo, valuta=valuta, importo_cassa=importo, quantita=qta or None, prezzo=prezzo or None,
                                            prezzo_in_percento=pct, importo_lordo=lordo, commissione=comm, strumento=strum, titolo=titolo)
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
    msg = st.session_state.pop("cli_msg", None)
    if msg:
        st.success(msg[0])
        for a in msg[1]:
            st.warning(a)
    t0, t1, t2, t3 = st.tabs(["Prodotti", "Estratti conto", "Movimenti", "Dati cliente"])
    with t0:
        _prodotti(c, reg)
    with t1:
        _estratti(c, reg)
    with t2:
        _movimenti(c, reg)
        _deposito(c, reg)
    with t3:
        _dati(c)
