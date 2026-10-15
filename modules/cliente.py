import pandas as pd
import streamlit as st

from core import dati
from core.config import VALUTE_BASE
from core.nav import vai
from core.importatore import leggi_documento
from core.stile import bottone, intestazione

VALUTE = ["CHF", "EUR", "USD", "GBP", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"]


def _stato_prodotto(v, k):
    tx = [t for t in v["transazioni"] if t.get("strumento") == k]
    qta = sum((t.get("quantita") or 0) * (1 if t["tipo"] == "acquisto" else -1) for t in tx if t["tipo"] in ("acquisto", "vendita", "rimborso"))
    return "attivo" if qta > 1e-9 else "chiuso"


def _prodotti(c, reg, pf):
    from core.completezza import problemi_strumento, prodotti_del_cliente
    from modules import scheda_prodotto as sp
    v = dati.vista_portafoglio(c, pf["id"])
    st.caption("Qui completi le condizioni dei prodotti già acquistati (scadenza, cedola, barriera, sottostanti). Poi il programma legge solo i dati reali.")
    prod = prodotti_del_cliente(v, reg)
    if not prod:
        st.info("Nessun prodotto acquistato in questo portafoglio.")
    for k, s in sorted(prod.items(), key=lambda x: (_stato_prodotto(v, x[0]), x[1].get("nome", ""))):
        pr = problemi_strumento(s)
        bl = sum(1 for g, _ in pr if g == "bloccante")
        badge = "🔴 da completare" if bl else "✓ completo"
        with st.expander(f"{s.get('nome') or k} · {_stato_prodotto(v, k)} · {badge}", expanded=bool(bl) and len(prod) <= 3):
            sp.scheda(reg, k, v, 'p' + pf['id'])
    with st.expander("➕ Aggiungi un acquisto a mano"):
        _nuovo_prodotto(c, reg, pf)


def _nuovo_prodotto(c, reg, pf):
    from modules import scheda_prodotto as sp
    from core.stile import bottone
    pid = pf["id"]
    esistenti = [""] + sorted(reg.strumenti, key=lambda k: reg.strumenti[k].get("nome", ""))
    k0 = st.selectbox("Prodotto già in anagrafica", esistenti, format_func=lambda k: reg.strumenti[k]["nome"] if k else "➕ Nuovo prodotto…", key=f"ac_{pid}_es")
    v = None
    if not k0:
        v = sp.campi_prodotto(f"ac_{pid}", {"valuta": c["valuta_base"]})
        valuta, pct = v["valuta"], v["prezzo_in_percento"]
    else:
        valuta, pct = reg.strumenti[k0]["valuta"], bool(reg.strumenti[k0].get("prezzo_in_percento"))
    st.markdown("**Acquisto**")
    a1, a2, a3, a4 = st.columns(4)
    data = a1.date_input("Data acquisto", format="DD.MM.YYYY", key=f"ac_{pid}_data")
    qta = a2.number_input("Quantità / nominale", min_value=0.0, value=0.0, format="%.4f", key=f"ac_{pid}_q")
    prezzo = a3.number_input("Prezzo (% del nominale)" if pct else "Prezzo", min_value=0.0, value=0.0, format="%.4f", key=f"ac_{pid}_p")
    comm = a4.number_input("Commissioni + tasse", min_value=0.0, value=0.0, format="%.2f", key=f"ac_{pid}_c")
    lordo = qta * prezzo / (100 if pct else 1)
    st.info(f"Importo addebitato calcolato: **{lordo + comm:,.2f} {valuta}**".replace(",", "’"))
    if bottone("Registra l'acquisto", "verde", f"ac_{pid}_ok"):
        if qta <= 0 or prezzo <= 0 or (v is not None and not v["nome"].strip()):
            st.error("Servono nome (se nuovo), quantità e prezzo.")
            return
        k = k0 or sp.crea_prodotto(reg, v)
        dati.aggiungi_movimento_manuale(c, data=str(data), tipo="acquisto", valuta=valuta, importo_cassa=-(lordo + comm), quantita=qta, prezzo=prezzo,
                                        prezzo_in_percento=pct, importo_lordo=lordo, commissione=comm, strumento=k, titolo=f"Acquisto {reg.strumenti[k]['nome']}", portafoglio=pid)
        pf["stato"] = "attivo"
        dati.salva_cliente(c)
        dati.salva_registro(reg)
        st.session_state["cli_msg"] = ("Acquisto registrato.", [])
        st.rerun()


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


def _estratti(c, reg, pf):
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
    if pronti and bottone("Conferma e importa le righe selezionate", "verde", "cli_importa"):
        from core import revisione
        n = d = 0
        avvisi, prima = [], set(reg.strumenti)
        for tipo, nome, doc, righe in pronti:
            if tipo == "movimenti":
                r = dati.importa_in_portafoglio(c, pf["id"], dati.importa_estratto, revisione.applica_modifiche(doc, righe), reg)
            else:
                r = dati.importa_in_portafoglio(c, pf["id"], dati.importa_posizioni, revisione.applica_modifiche_posizioni(doc, righe), reg)
            n += r["nuovi"]; d += r["duplicati"]; avvisi += r.get("avvisi", [])
        pf["stato"] = "attivo"
        dati.salva_cliente(c)
        dati.salva_registro(reg)
        for k in ("cli_upload",):
            st.session_state.pop(k, None)
        nuovi = sorted(set(reg.strumenti) - prima)
        st.session_state["cli_msg"] = (f"Importati {n} elementi ({d} già presenti). " + (f"{len(nuovi)} prodotti nuovi: completa le condizioni in «Prodotti»." if nuovi else ""), avvisi)
        st.rerun()
    if c.get("estratti"):
        st.markdown("**Documenti già importati** (di tutti i portafogli del cliente)")
        st.dataframe(pd.DataFrame(c["estratti"]), hide_index=True, width="stretch")


def _movimenti(c, reg, pf):
    tx = dati.transazioni_ordinate(dati.vista_portafoglio(c, pf["id"]))
    if tx:
        righe = [{"id": t["id"], "Elimina": False, "Data": t["data"], "Tipo": dati.ETICHETTE_TIPO.get(t["tipo"], t["tipo"]),
                  "Strumento": (reg.strumenti.get(t.get("strumento")) or {}).get("nome") or t.get("titolo", ""),
                  "Quantità": t.get("quantita"), "Prezzo": t.get("prezzo"), "Valuta": t["valuta"], "Importo": t.get("importo_cassa"), "Origine": t.get("fonte", "")} for t in tx]
        ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key="cli_mov_ed", column_config={"id": None},
                            disabled=["Tipo", "Strumento", "Valuta", "Origine"])
        if bottone("Salva modifiche ai movimenti", "verde", "cli_mov_salva"):
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
        if bottone("Aggiungi movimento", "verde", "mm_add"):
            dati.aggiungi_movimento_manuale(c, data=str(data), tipo=tipo, valuta=valuta, importo_cassa=importo, quantita=qta or None, prezzo=prezzo or None,
                                            prezzo_in_percento=pct, importo_lordo=lordo, commissione=comm, strumento=strum, titolo=titolo, portafoglio=pf["id"])
            dati.salva_cliente(c)
            st.rerun()


def _deposito(c, reg, pf):
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
                dati.importa_in_portafoglio(c, pf["id"], lambda cl: dati.aggiungi_deposito_termine(cl, reg, banca, numero or "n/d", valuta, nominale, tasso, str(inizio), str(fine), lordo, imposta) or {})
                dati.salva_cliente(c)
                dati.salva_registro(reg)
                st.success("Deposito registrato (acquisto, interesse, imposta, rimborso).")


def _dati(c):
    with st.container(border=True):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome", c.get("nome_proprio", c["nome"]), key="dc_nome")
        cognome = c2.text_input("Cognome", c.get("cognome", ""), key="dc_cogn")
        c1, c2 = st.columns(2)
        valuta = c1.selectbox("Valuta di riferimento", VALUTE_BASE, index=VALUTE_BASE.index(c["valuta_base"]) if c["valuta_base"] in VALUTE_BASE else 0, key="dc_val")
        rischio = c2.selectbox("Grado di rischio (1 basso – 5 alto)", [1, 2, 3, 4, 5], index=int(c.get("rischio", 2)) - 1, key="dc_risc")
        note = st.text_area("Note", c.get("note", ""), key="dc_note")
        if bottone("Salva", "verde", "dc_salva"):
            c.update(nome=f"{nome.strip()} {cognome.strip()}".strip() or c["nome"], nome_proprio=nome.strip(), cognome=cognome.strip(), valuta_base=valuta, rischio=rischio, note=note)
            dati.salva_cliente(c)
            st.success("Salvato.")
    with st.expander("Elimina cliente"):
        conf = st.checkbox("Confermo: eliminare il cliente e tutti i suoi portafogli e movimenti", key="cli_conf_elim")
        if bottone("Elimina definitivamente", "rosso", "cli_elimina", disabled=not conf):
            dati.elimina_cliente(c["id"])
            st.session_state.pop("cli_id", None)
            vai("clienti")


def _selettore_portafoglio(c):
    pfs = dati.assicura_portafogli(c)
    with st.container(border=True):
        a, b = st.columns([3, 1], vertical_alignment="bottom")
        if pfs:
            ids = [p["id"] for p in pfs]
            pre = st.session_state.get("cli_pf")
            if pre not in ids:
                pre = ids[0]
            st.session_state["cli_pf"] = a.selectbox("Portafoglio", ids, index=ids.index(pre), key="cli_pf_sel",
                                                     format_func=lambda i: next(f"{p['nome']} · {'attivo' if p['stato'] == 'attivo' else 'in strategia'}" for p in pfs if p["id"] == i))
        else:
            a.info("Nessun portafoglio: crea la prima strategia per questo cliente.")
        with b.popover("➕ Nuova strategia", width="stretch"):
            nome = st.text_input("Nome", f"Strategia {len(pfs) + 1}", key="npf_nome")
            cap = st.number_input(f"Capitale ({c['valuta_base']})", min_value=0.0, value=0.0, step=1000.0, key="npf_cap")
            if bottone("Crea", "verde", "npf_crea"):
                pf = dati.nuovo_portafoglio(c, nome, cap)
                dati.salva_cliente(c)
                st.session_state["cli_pf"] = pf["id"]
                st.rerun()
    return dati.portafoglio(c, st.session_state.get("cli_pf")) if pfs else None


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
    pf = _selettore_portafoglio(c)
    if pf is None:
        _dati(c)
        return
    from modules import andamento, strategia
    t = st.tabs(["Strategia", "Andamento", "Prodotti", "Estratti conto", "Movimenti", "Cliente"])
    with t[0]:
        strategia.render(c, reg, pf)
    with t[1]:
        andamento.render(c, reg, pf)
    with t[2]:
        _prodotti(c, reg, pf)
    with t[3]:
        _estratti(c, reg, pf)
    with t[4]:
        _movimenti(c, reg, pf)
        _deposito(c, reg, pf)
    with t[5]:
        _dati(c)
