"""Strategia = portafoglio del cliente, sempre aggiornato: prodotti, incassi, costi, performance in diretta e documenti."""

from __future__ import annotations

from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from core import dati, live, strategia as stg
from core.config import CATEGORIE
from core.stile import bottone
from modules import scheda_prodotto as sp

VALUTE = ["CHF", "EUR", "USD", "GBP", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"]


@st.cache_data(ttl=3600, show_spinner=False)
def _fx_oggi(da: str, a: str):
    from core.mercato import mercato_reale
    return mercato_reale().fx(da, a, date.today().isoformat())


def _cerca(da, a):
    return _fx_oggi(da, a)


def _e(x, d=0):
    return "–" if x is None else f"{x:,.{d}f}".replace(",", "’")


def _p(x, d=2):
    return "n.d." if x is None else f"{100 * x:+.{d}f}%"


def _live(c, reg, pf, forza=False):
    """Ricalcola lo stato in diretta quando cambiano i dati (o su richiesta) e lo salva nel cliente."""
    f = live.firma(c, pf, reg)
    chiave = f"lv_{pf['id']}"
    L = pf.get("live") or {}
    if forza or (L.get("firma") != f and st.session_state.get(chiave) != f):
        st.session_state[chiave] = f
        with st.spinner("Aggiorno prezzi e performance…"):
            live.aggiorna(c, pf, reg)
            dati.salva_cliente(c)
    return pf.get("live") or {}


def torta(valori: dict, etichette: dict | None = None):
    voci = {(etichette or {}).get(k, k): v for k, v in valori.items() if v and v > 0}
    if not voci:
        st.caption("Nessun dato.")
        return
    df = pd.DataFrame({"Voce": list(voci), "Valore": list(voci.values())})
    df["Quota"] = df["Valore"] / df["Valore"].sum()
    ch = alt.Chart(df).mark_arc(innerRadius=55, stroke="#000000").encode(
        theta="Valore:Q", color=alt.Color("Voce:N", legend=alt.Legend(orient="right", labelColor="#F2F2F2", title=None)),
        tooltip=["Voce", alt.Tooltip("Valore:Q", format=",.0f"), alt.Tooltip("Quota:Q", format=".1%")]).properties(height=240)
    st.altair_chart(ch, width="stretch")


def linea(serie, titolo="Performance dall'inizio (%)"):
    if len(serie) < 2:
        st.caption("Il grafico compare quando ci sono almeno due date di calcolo (dopo il primo mese).")
        return
    df = pd.DataFrame(serie, columns=["Data", titolo]).set_index("Data")
    st.line_chart(df, height=240)


def _testata(c, pf):
    with st.container(border=True):
        a, b, d = st.columns([2, 1, 1])
        nome = a.text_input("Nome della strategia", pf["nome"], key=f"st_nome_{pf['id']}")
        cap = b.number_input(f"Capitale da investire ({pf['valuta']}) – facoltativo", min_value=0.0, value=float(pf.get("capitale") or 0.0), step=1000.0, format="%.2f", key=f"st_cap_{pf['id']}")
        val = d.selectbox("Valuta del portafoglio", VALUTE, index=VALUTE.index(pf["valuta"]) if pf["valuta"] in VALUTE else 0, key=f"st_val_{pf['id']}")
        s1, s2, _ = st.columns([1, 1, 3])
        with s1:
            if bottone("Salva", "verde", f"st_savetest_{pf['id']}", width="stretch"):
                pf.update(nome=nome.strip() or pf["nome"], capitale=cap, valuta=val)
                dati.salva_cliente(c)
                st.rerun()
        with s2:
            if bottone("Elimina strategia", "rosso", f"st_delpf_{pf['id']}", width="stretch"):
                st.session_state[f"st_delask_{pf['id']}"] = True
        if st.session_state.get(f"st_delask_{pf['id']}"):
            st.warning(f"Eliminare «{pf['nome']}» e tutti i suoi movimenti? Non si può annullare.")
            y1, y2, _ = st.columns([1, 1, 3])
            with y1:
                if bottone("Sì, elimina", "rosso", f"st_delpf_ok_{pf['id']}", width="stretch"):
                    c["transazioni"] = [t for t in c["transazioni"] if dati._pf_di(c, t) != pf["id"]]
                    c["saldi"] = [t for t in c["saldi"] if dati._pf_di(c, t) != pf["id"]]
                    c["portafogli"] = [p for p in c["portafogli"] if p["id"] != pf["id"]]
                    dati.salva_cliente(c)
                    st.session_state.pop("cli_pf", None)
                    st.rerun()
            with y2:
                if st.button("Annulla", key=f"st_delpf_no_{pf['id']}", width="stretch"):
                    st.session_state.pop(f"st_delask_{pf['id']}", None)
                    st.rerun()


def _panoramica(c, reg, pf, calc):
    L = _live(c, reg, pf)
    base = pf["valuta"]
    cA, cB = st.columns([5, 1], vertical_alignment="bottom")
    cA.markdown("#### Panoramica in diretta")
    if cB.button("Aggiorna prezzi", key=f"st_agg_{pf['id']}", width="stretch"):
        _live(c, reg, pf, forza=True)
        st.rerun()
    if L.get("vuoto"):
        st.info("Nessun prodotto: aggiungi il primo qui sotto.")
        return L
    if L.get("errore"):
        st.warning(f"Prezzi di mercato non disponibili al momento ({L['errore']}). Mostro l'ultimo calcolo valido e gli importi investiti.")
    k = st.columns(5)
    k[0].metric("Valore del portafoglio", f"{base} {_e(L.get('valore'))}" if L.get("valore") is not None else "–")
    k[1].metric("Investito", f"{base} {_e(L.get('investito') if L.get('investito') is not None else calc['totale'])}")
    k[2].metric("Cedole e proventi incassati", f"{base} {_e(L.get('proventi'))}" if L.get("proventi") is not None else "–")
    k[3].metric("Performance dall'inizio", _p(L.get("perf")))
    k[4].metric("Annualizzata", _p(L.get("xirr")))
    for a in (L.get("avvisi") or [])[:4]:
        st.caption(f"⚠ {a}")
    g1, g2 = st.columns(2)
    with g1:
        st.caption("Allocazione")
        torta(L.get("allocazione") or calc["allocazione"], CATEGORIE | {"liquidita": "Liquidità"})
    with g2:
        st.caption("Andamento della performance")
        linea(L.get("serie") or [])
    return L


# ───────────────────────── tabella dei prodotti (modificabile) ─────────────────────────
def _tabella(c, reg, pf, calc, L):
    righe_calc = calc["righe"]
    if not righe_calc:
        return
    prezzi_att = (L or {}).get("prezzi") or {}
    righe = []
    for x in righe_calc:
        s = reg.strumenti[x["strumento"]]
        navs = sorted(s.get("nav_manuale", []), key=lambda n: n["data"])
        att = prezzi_att.get(x["strumento"], navs[-1]["nav"] if navs else None)
        righe.append({"id": x["id"], "Elimina": False, "Prodotto": x["nome"], "Tipo": CATEGORIE.get(x["categoria"], ""), "Valuta": x["valuta"],
                      "Data acquisto": date.fromisoformat(x["data"]), "Investito": round(x["importo"], 2), "Prezzo acquisto": x["prezzo"],
                      "Quantità / nominale": x["quantita"], "Commissioni": round(x["commissioni"], 2), "Prezzo attuale": att,
                      "Peso %": round(x["peso_eff_pct"], 1), "Stato": "attivo" if x["attivo"] else "chiuso"})
    orig = {r["id"]: dict(r) for r in righe}
    st.markdown("#### Prodotti")
    st.caption("Modifica direttamente nella tabella: se cambi **Investito** la quantità si ricalcola dal prezzo; se cambi prezzo o quantità l'investito si ricalcola. "
               "Prezzo in % del nominale per obbligazioni e strutturati. **Prezzo attuale** è modificabile per obbligazioni e fondi a prezzo manuale (resta in % per le obbligazioni).")
    ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key=f"st_tab_{pf['id']}", column_config={
        "id": None, "Elimina": st.column_config.CheckboxColumn(width="small"), "Data acquisto": st.column_config.DateColumn(format="DD.MM.YYYY"),
        "Investito": st.column_config.NumberColumn(format="%.2f"), "Prezzo acquisto": st.column_config.NumberColumn(format="%.4f"),
        "Quantità / nominale": st.column_config.NumberColumn(format="%.4f"), "Commissioni": st.column_config.NumberColumn(format="%.2f"),
        "Prezzo attuale": st.column_config.NumberColumn(format="%.4f"), "Peso %": st.column_config.NumberColumn(format="%.1f")},
        disabled=["Prodotto", "Tipo", "Valuta", "Peso %", "Stato"])
    b1, b2, _ = st.columns([1, 1, 3])
    with b1:
        if bottone("Salva modifiche", "verde", f"st_tabsave_{pf['id']}", width="stretch"):
            per_id = {t["id"]: t for t in c["transazioni"]}
            n_el = 0
            for r in ed.to_dict("records"):
                tx = per_id.get(r["id"])
                if not tx:
                    continue
                if r["Elimina"]:
                    c["transazioni"].remove(tx); n_el += 1
                    continue
                o = orig[r["id"]]
                s = reg.strumenti[tx["strumento"]]
                diff = lambda k_: abs((r[k_] or 0) - (o[k_] or 0)) > 1e-9
                data = r["Data acquisto"].isoformat() if hasattr(r["Data acquisto"], "isoformat") else str(r["Data acquisto"])
                stg.modifica_acquisto(tx, s, data=data if data != o["Data acquisto"].isoformat() else None,
                                      prezzo=float(r["Prezzo acquisto"]) if diff("Prezzo acquisto") else None,
                                      quantita=float(r["Quantità / nominale"]) if diff("Quantità / nominale") else None,
                                      investito=float(r["Investito"]) if diff("Investito") and not diff("Quantità / nominale") else None,
                                      commissioni=float(r["Commissioni"]) if diff("Commissioni") else None)
                if diff("Prezzo attuale") and r["Prezzo attuale"] is not None and r["Prezzo attuale"] == r["Prezzo attuale"]:
                    if s.get("valutazione") == "manuale":
                        s["nav_manuale"] = [n for n in s.get("nav_manuale", []) if n["data"] != date.today().isoformat()] + [{"data": date.today().isoformat(), "nav": float(r["Prezzo attuale"])}]
                    else:
                        st.warning(f"{s['nome']}: il prezzo attuale non è modificabile (si legge da Yahoo o è al 100% del nominale).")
            dati.salva_cliente(c); dati.salva_registro(reg)
            st.rerun()
    with b2:
        if bottone("Elimina le righe spuntate", "rosso", f"st_tabdel_{pf['id']}", width="stretch"):
            ids = {r["id"] for r in ed.to_dict("records") if r["Elimina"]}
            c["transazioni"] = [t for t in c["transazioni"] if t["id"] not in ids]
            dati.salva_cliente(c)
            st.rerun()


# ───────────────────────── aggiunta di un nuovo prodotto ─────────────────────────
def _nuovo_prodotto(c, reg, pf):
    pid = f"np_{pf['id']}"
    v = sp.campi_prodotto(pid, {"valuta": pf["valuta"]})
    pct, valuta, cat = v["prezzo_in_percento"], v["valuta"], v["categoria"]
    st.markdown("**Investimento**")
    modi = ["Importo investito", "Quantità / nominale"]
    modo = st.radio("Cosa conosci?", modi, index=1 if cat in ("etf_azioni", "opzione") else 0, horizontal=True, key=f"{pid}_modo_{cat}")
    a1, a2, a3, a4 = st.columns(4)
    data = a1.date_input("Data di acquisto", format="DD.MM.YYYY", key=f"{pid}_data")
    k_ = f"{pid}_{cat}_{int(pct)}"
    prezzo = a2.number_input("Prezzo di acquisto (% del nominale)" if pct else "Prezzo di acquisto (per unità)", min_value=0.0, value=100.0 if pct else 0.0, format="%.4f", key=f"{k_}_p")
    if modo == modi[0]:
        inv = a3.number_input(f"Importo investito ({valuta})", min_value=0.0, value=0.0, step=1000.0, format="%.2f", key=f"{k_}_inv")
        qta = stg.quantita_da_investito(inv, prezzo, pct)
    else:
        qta = a3.number_input("Quantità / nominale", min_value=0.0, value=0.0, format="%.4f", key=f"{k_}_q")
        inv = stg.lordo(qta, prezzo, pct)
    comm = a4.number_input("Costo di acquisto (commissioni, tasse)", min_value=0.0, value=0.0, format="%.2f", key=f"{k_}_c")
    st.info(f"Quantità / nominale **{_e(qta, 4).rstrip('0').rstrip('.')}** · investito **{valuta} {_e(inv, 2)}** · addebitato **{valuta} {_e(inv + comm, 2)}**")
    if bottone("Aggiungi il prodotto", "verde", f"{pid}_ok"):
        if not v["nome"].strip() or qta <= 0 or prezzo <= 0:
            st.error("Servono nome, prezzo e importo (o quantità).")
            return
        k = sp.crea_prodotto(reg, v)
        stg.aggiungi_acquisto(c, pf, reg, k, data.isoformat(), prezzo, comm, quantita=qta)
        dati.salva_cliente(c); dati.salva_registro(reg)
        st.session_state["cli_msg"] = (f"«{v['nome']}» aggiunto al portafoglio.", [])
        st.rerun()


def _da_screenshot(c, reg, pf):
    from core import parser_ibkr
    st.caption("Carica uno screenshot (o un PDF) della pagina Portfolio → Positions di Interactive Brokers: leggo simboli, quantità e costi. Controlla la tabella prima di importare.")
    f = st.file_uploader("Screenshot o PDF", type=["png", "jpg", "jpeg", "pdf"], key=f"ib_up_{pf['id']}")
    if not f:
        return
    try:
        pos = parser_ibkr.leggi(f)
    except Exception as e:
        st.error(f"Non riesco a leggere il file: {e}")
        return
    from core.anagrafica import classifica_da_nome
    gia = {(x["strumento"], round(x["quantita"], 6)) for x in stg.calcola(c, pf, reg)["righe"]}
    righe = []
    for i, p in enumerate(pos):
        cat, sub = classifica_da_nome(p.nome)
        k = reg.trova("", p.simbolo)
        esiste = bool(k and (k, round(p.quantita, 6)) in gia)
        pe = p.prezzo_effettivo()
        ok = bool(p.costo_totale and p.quantita and p.prezzo_medio and abs(p.quantita * p.prezzo_medio - p.costo_totale) <= max(0.01 * p.costo_totale, 1))
        righe.append({"_i": i, "Importa": not esiste, "Simbolo": p.simbolo, "Nome": p.nome, "Tipo": "ETF" if (sub or "").startswith("ETF") or "ETF" in p.nome.upper() or "ISHARES" in p.nome.upper() or "UCITS" in p.nome.upper() else "Azione",
                      "Valuta": p.valuta, "Quantità": p.quantita, "Costo totale": p.costo_totale, "Prezzo medio": round(pe, 4) if pe else None, "Data acquisto": date.today(),
                      "Controllo": "già presente" if esiste else ("✓" if ok else "⚠ controlla")})
    ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key=f"ib_ed_{pf['id']}", disabled=["Controllo"],
                        column_config={"_i": None, "Tipo": st.column_config.SelectboxColumn(options=["Azione", "ETF"]), "Valuta": st.column_config.SelectboxColumn(options=VALUTE),
                                       "Data acquisto": st.column_config.DateColumn(format="DD.MM.YYYY")})
    st.caption("Data di acquisto: lo screenshot non la contiene, quindi parte da oggi. Impostala per ogni riga. Il prezzo è il costo totale diviso la quantità.")
    if bottone("Importa le righe spuntate", "verde", f"ib_ok_{pf['id']}"):
        n = 0
        for r in ed.to_dict("records"):
            if not r["Importa"] or not r["Quantità"] or not r["Costo totale"]:
                continue
            k = reg.trova("", r["Simbolo"]) or reg.assicura("", r["Simbolo"], r["Nome"], r["Valuta"], False)
            s = reg.strumenti[k]
            s.update(categoria="etf_azioni", sottocategoria="ETF azionario" if r["Tipo"] == "ETF" else "Azione ordinaria", valuta=r["Valuta"], valutazione="mercato", prezzo_in_percento=False)
            if r["Valuta"] == "USD" and not s.get("ticker_mercato"):
                s["ticker_mercato"] = r["Simbolo"]
            d = r["Data acquisto"]
            stg.aggiungi_acquisto(c, pf, reg, k, d.isoformat() if hasattr(d, "isoformat") else str(d), r["Costo totale"] / r["Quantità"], 0.0, quantita=float(r["Quantità"]))
            n += 1
        dati.completa_strumenti(c, reg, nuovi_solo=set(reg.strumenti))
        dati.salva_cliente(c); dati.salva_registro(reg)
        st.session_state["cli_msg"] = (f"Importate {n} posizioni. I ticker degli ETF in euro vanno completati in «Prodotti» per avere i prezzi in diretta.", [])
        st.rerun()


# ───────────────────────── incassi e costi ─────────────────────────
def _incassi_costi(c, reg, pf, calc):
    prodotti = {x["strumento"]: x["nome"] for x in calc["righe"]}
    t1, t2 = st.tabs(["Cedola, interesse, dividendo, premio", "Costi (custodia, spese, imposte)"])
    with t1:
        if not prodotti:
            st.info("Aggiungi prima un prodotto.")
        else:
            a, b, d = st.columns(3)
            k = a.selectbox("Prodotto", list(prodotti), format_func=lambda x: prodotti[x], key=f"inc_k_{pf['id']}")
            tipo = b.selectbox("Cosa hai ricevuto", list(stg.TIPI_INCASSO), format_func=lambda x: stg.TIPI_INCASSO[x], key=f"inc_t_{pf['id']}")
            data = d.date_input("Data", format="DD.MM.YYYY", key=f"inc_d_{pf['id']}")
            e, f_, g = st.columns(3)
            imp = e.number_input(f"Importo ricevuto ({reg.strumenti[k]['valuta']})", min_value=0.0, value=0.0, format="%.2f", key=f"inc_i_{pf['id']}")
            tax = f_.number_input("Imposta trattenuta (facoltativa)", min_value=0.0, value=0.0, format="%.2f", key=f"inc_x_{pf['id']}")
            nota = g.text_input("Nota (es. cedola 2° trimestre)", key=f"inc_n_{pf['id']}")
            if bottone("Registra l'incasso", "verde", f"inc_ok_{pf['id']}"):
                if imp <= 0:
                    st.error("Inserisci l'importo.")
                else:
                    stg.registra_incasso(c, pf, reg, k, tipo, data.isoformat(), imp, tax, nota)
                    dati.salva_cliente(c)
                    st.rerun()
    with t2:
        a, b, d = st.columns(3)
        tipo = a.selectbox("Tipo di costo", list(stg.TIPI_COSTO_UI), format_func=lambda x: stg.TIPI_COSTO_UI[x], key=f"cos_t_{pf['id']}")
        data = b.date_input("Data", format="DD.MM.YYYY", key=f"cos_d_{pf['id']}")
        val = d.selectbox("Valuta", VALUTE, index=VALUTE.index(pf["valuta"]) if pf["valuta"] in VALUTE else 0, key=f"cos_v_{pf['id']}")
        e, f_ = st.columns([1, 2])
        imp = e.number_input("Importo", min_value=0.0, value=0.0, format="%.2f", key=f"cos_i_{pf['id']}")
        desc = f_.text_input("Descrizione (facoltativa)", key=f"cos_n_{pf['id']}")
        if bottone("Registra il costo", "verde", f"cos_ok_{pf['id']}"):
            if imp <= 0:
                st.error("Inserisci l'importo.")
            else:
                stg.registra_costo(c, pf, tipo, data.isoformat(), imp, val, desc)
                dati.salva_cliente(c)
                st.rerun()
    v = dati.vista_portafoglio(c, pf["id"])
    movs = [t for t in dati.transazioni_ordinate(v) if t["tipo"] in list(stg.TIPI_INCASSO) + list(stg.TIPI_COSTO_UI)]
    if movs:
        st.markdown("**Incassi e costi registrati**")
        df = pd.DataFrame([{"id": t["id"], "Elimina": False, "Data": t["data"], "Tipo": dati.ETICHETTE_TIPO.get(t["tipo"], t["tipo"]), "Prodotto": (reg.strumenti.get(t.get("strumento")) or {}).get("nome", ""),
                            "Valuta": t["valuta"], "Importo": t["importo_cassa"], "Origine": t.get("fonte", "")} for t in movs])
        ed = st.data_editor(df, hide_index=True, width="stretch", key=f"inc_tab_{pf['id']}", column_config={"id": None}, disabled=["Tipo", "Prodotto", "Valuta", "Origine"])
        if bottone("Salva modifiche agli incassi e ai costi", "verde", f"inc_tabsave_{pf['id']}"):
            per_id = {t["id"]: t for t in c["transazioni"]}
            for r in ed.to_dict("records"):
                t = per_id[r["id"]]
                if r["Elimina"]:
                    c["transazioni"].remove(t)
                else:
                    t["data"] = t["data_valuta"] = str(r["Data"]); t["importo_cassa"] = float(r["Importo"])
            dati.salva_cliente(c)
            st.rerun()


def render(c, reg, pf):
    _testata(c, pf)
    calc = stg.calcola(c, pf, reg, _cerca)
    L = _panoramica(c, reg, pf, calc)
    for a in calc["avvisi"]:
        st.warning(a)
        v = a.split("Cambio ")[1].split("→")[0] if "Cambio " in a else None
        if v and v in VALUTE:
            pf.setdefault("cambi", {})[v] = st.number_input(f"Cambio {v} → {pf['valuta']}", min_value=0.0, value=float((pf.get("cambi") or {}).get(v) or 0.0), format="%.5f", key=f"st_fx_{pf['id']}_{v}") or None
    _tabella(c, reg, pf, calc, L)

    with st.expander("➕ Aggiungi un prodotto"):
        _nuovo_prodotto(c, reg, pf)
    with st.expander("📷 Aggiungi prodotti da screenshot o PDF (Interactive Brokers)"):
        _da_screenshot(c, reg, pf)
    with st.expander("💶 Registra cedole, interessi, premi e costi"):
        _incassi_costi(c, reg, pf, calc)

    st.markdown("#### Documenti")
    o1, o2, o3 = st.columns(3)
    from core.strategia_pdf import genera_pdf_strategia
    with o1:
        if st.button("Prepara il PDF della strategia", key=f"st_pdf_{pf['id']}", width="stretch"):
            st.session_state[f"st_pdfb_{pf['id']}"] = genera_pdf_strategia(c, pf, calc)
        if st.session_state.get(f"st_pdfb_{pf['id']}"):
            st.download_button("Scarica il PDF", st.session_state[f"st_pdfb_{pf['id']}"], file_name=f"Strategia_{c['nome'].replace(' ', '_')}_{date.today().isoformat()}.pdf",
                               mime="application/pdf", key=f"st_pdfd_{pf['id']}", width="stretch")
    with o2:
        if bottone("Crea il report", "blu", f"st_rep_{pf['id']}", width="stretch"):
            st.session_state[f"st_repopen_{pf['id']}"] = not st.session_state.get(f"st_repopen_{pf['id']}", False)
    with o3:
        testo = stg.testo_analisi(c, pf, calc)
        st.link_button("Analizza la strategia con Claude", stg.link_claude(testo), width="stretch")
    with st.expander("Testo inviato a Claude (puoi copiarlo in una chat o in un progetto fisso)"):
        st.code(testo, language=None)
        st.download_button("Scarica il testo (.txt)", testo, file_name="analisi_strategia.txt", key=f"st_txt_{pf['id']}")
        st.caption("Il pulsante apre una nuova chat di Claude con il testo già inserito. Per una chat fissa, crea un Progetto «Analisi strategie» su claude.ai e incolla il testo.")
    if st.session_state.get(f"st_repopen_{pf['id']}"):
        from modules import report
        with st.container(border=True):
            st.markdown("#### Report per il cliente")
            report.pannello(c, reg, pf)
