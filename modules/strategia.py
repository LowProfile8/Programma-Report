"""Fase 2 — Strategia: prodotti proposti, pesi, prezzi e quantità; PDF per il cliente; analisi con Claude; creazione del portafoglio."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import dati, strategia as stg
from core.config import CATEGORIE
from core.stile import bottone
from modules import scheda_prodotto as sp


@st.cache_data(ttl=3600, show_spinner=False)
def _fx_oggi(da: str, a: str):
    from core.mercato import mercato_reale
    return mercato_reale().fx(da, a, date.today().isoformat())


def _cerca(da, a):
    return _fx_oggi(da, a)


def _e(x, d=0):
    return f"{x:,.{d}f}".replace(",", "’")


def render(c, reg, pf):
    attivo = pf["stato"] == "attivo"
    if attivo:
        st.info("Questo portafoglio è già attivo: la strategia qui sotto è quella di partenza. I nuovi movimenti si registrano dagli estratti conto.")

    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        pf["nome"] = c1.text_input("Nome della strategia / portafoglio", pf["nome"], key=f"st_nome_{pf['id']}")
        pf["capitale"] = c2.number_input(f"Capitale da investire ({pf['valuta']})", min_value=0.0, value=float(pf["capitale"]), step=1000.0, format="%.2f", key=f"st_cap_{pf['id']}")
        valute = ["CHF", "EUR", "USD"]
        pf["valuta"] = c3.selectbox("Valuta del portafoglio", valute, index=valute.index(pf["valuta"]) if pf["valuta"] in valute else 0, key=f"st_val_{pf['id']}", disabled=attivo)

    # ── aggiunta prodotti ──
    usati = {r["strumento"] for r in pf["righe"]}
    disponibili = sorted((k for k in reg.strumenti if k not in usati and reg.strumenti[k].get("categoria") != "liquidita"), key=lambda k: reg.strumenti[k].get("nome", ""))
    if not attivo:
        a1, a2 = st.columns([3, 1], vertical_alignment="bottom")
        scelto = a1.selectbox("Aggiungi un prodotto già in anagrafica", [""] + disponibili, format_func=lambda k: (reg.strumenti[k]["nome"] + f" · {CATEGORIE.get(reg.strumenti[k]['categoria'], '')}") if k else "—", key=f"st_agg_{pf['id']}")
        if a2.button("Aggiungi", key=f"st_aggbtn_{pf['id']}", width="stretch") and scelto:
            pf["righe"].append(stg.nuova_riga(scelto))
            dati.salva_cliente(c)
            st.rerun()
        with st.expander("➕ Crea un nuovo prodotto"):
            k = sp.nuovo(reg, f"np_{pf['id']}")
            if k:
                pf["righe"].append(stg.nuova_riga(k))
                dati.salva_cliente(c)
                st.session_state["cli_msg"] = (f"Prodotto «{reg.strumenti[k]['nome']}» creato e aggiunto alla strategia.", [])
                st.rerun()

    if not pf["righe"]:
        st.info("La strategia è vuota: aggiungi i prodotti che vuoi proporre.")
        return

    calc = stg.calcola(pf, reg, _cerca, solo_attive=False)
    per_id = {x["id"]: x for x in calc["righe"]}

    # ── tabella modificabile ──
    st.markdown("#### Prodotti della strategia")
    st.caption("Peso, prezzo e quantità sono quelli *proposti*. Il giorno dell'acquisto aggiornali con i valori reali. Prezzo in % del nominale per obbligazioni e strutturati.")
    righe = []
    for r in pf["righe"]:
        x = per_id.get(r["id"], {})
        s = reg.strumenti.get(r["strumento"], {})
        righe.append({"id": r["id"], "Elimina": False, "Prodotto": s.get("nome", r["strumento"]), "Tipo": CATEGORIE.get(s.get("categoria"), ""), "Valuta": s.get("valuta", ""),
                      "Peso %": r.get("peso_pct") or 0.0, "Prezzo": r.get("prezzo") or 0.0, "Quantità": r.get("quantita") or 0.0, "Commissioni": r.get("commissioni") or 0.0,
                      "Data acquisto": date.fromisoformat(r["data"]) if r.get("data") else date.today(), "Stato": r.get("stato", "proposto"),
                      "Importo": x.get("importo", 0.0), "Peso effettivo %": x.get("peso_eff_pct", 0.0)})
    ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key=f"st_ed_{pf['id']}", column_config={
        "id": None, "Elimina": st.column_config.CheckboxColumn(width="small"),
        "Stato": st.column_config.SelectboxColumn(options=list(stg.STATI), required=True),
        "Peso %": st.column_config.NumberColumn(format="%.2f"), "Prezzo": st.column_config.NumberColumn(format="%.4f"),
        "Quantità": st.column_config.NumberColumn(format="%.4f"), "Commissioni": st.column_config.NumberColumn(format="%.2f"),
        "Data acquisto": st.column_config.DateColumn(format="DD.MM.YYYY"), "Importo": st.column_config.NumberColumn(format="%.2f"),
        "Peso effettivo %": st.column_config.NumberColumn(format="%.1f")},
        disabled=["Prodotto", "Tipo", "Valuta", "Importo", "Peso effettivo %"] + (["Peso %"] if False else []))

    def _applica():
        for rec in ed.to_dict("records"):
            r = next(x for x in pf["righe"] if x["id"] == rec["id"])
            r.update(peso_pct=float(rec["Peso %"] or 0), prezzo=float(rec["Prezzo"] or 0), quantita=float(rec["Quantità"] or 0), commissioni=float(rec["Commissioni"] or 0),
                     data=rec["Data acquisto"].isoformat() if hasattr(rec["Data acquisto"], "isoformat") else str(rec["Data acquisto"]), stato=rec["Stato"])

    b1, b2, b3 = st.columns(3)
    with b1:
        if bottone("Salva modifiche", "verde", f"st_salva_{pf['id']}", width="stretch"):
            _applica(); dati.salva_cliente(c); st.success("Strategia salvata."); st.rerun()
    with b2:
        if bottone("Calcola quantità dai pesi", "giallo", f"st_qta_{pf['id']}", width="stretch"):
            _applica(); stg.quantita_da_pesi(pf, reg, _cerca); dati.salva_cliente(c); st.rerun()
    with b3:
        if bottone("Elimina i prodotti spuntati", "rosso", f"st_del_{pf['id']}", width="stretch"):
            ids = {rec["id"] for rec in ed.to_dict("records") if rec["Elimina"]}
            if ids:
                _applica(); pf["righe"] = [r for r in pf["righe"] if r["id"] not in ids]; dati.salva_cliente(c); st.rerun()

    with st.expander("Scheda dei singoli prodotti (condizioni, settore, area)"):
        for r in pf["righe"]:
            k = r["strumento"]
            with st.expander(reg.strumenti[k]["nome"]):
                sp.scheda(reg, k, None, 's' + pf['id'])

    # ── riepilogo ──
    calc = stg.calcola(pf, reg, _cerca)
    for a in calc["avvisi"]:
        st.warning(a)
    esteri = sorted({x["valuta"] for x in calc["righe"] if x["valuta"] != pf["valuta"] and not x["tasso"] != 1.0})
    for v in esteri:
        pf.setdefault("cambi", {})[v] = st.number_input(f"Cambio {v} → {pf['valuta']} (inserito a mano)", min_value=0.0, value=float((pf.get("cambi") or {}).get(v) or 0.0), format="%.5f", key=f"st_fx_{pf['id']}_{v}") or None
    k = st.columns(4)
    k[0].metric("Investito", f"{pf['valuta']} {_e(calc['totale'])}")
    k[1].metric("Peso totale", f"{calc['peso_totale_pct']:.1f}%")
    k[2].metric("Liquidità residua", f"{pf['valuta']} {_e(calc['liquidita_residua'])}")
    k[3].metric("Reddito annuo atteso" + (f" ({100 * calc['rendimento_cedolare']:.1f}%)" if calc["rendimento_cedolare"] else ""), f"{pf['valuta']} {_e(calc['reddito_annuo'])}")
    if abs(calc["peso_totale_pct"] - 100) > 0.5:
        st.caption(f"Nota: i pesi proposti sommano {calc['peso_totale_pct']:.1f}%; il resto resta in liquidità.")
    if calc["totale"]:
        g1, g2, g3 = st.columns(3)
        g1.caption("Per tipo di investimento")
        g1.bar_chart(pd.Series({CATEGORIE.get(k_, k_): v for k_, v in calc["allocazione"].items()}), height=220)
        g2.caption("Per settore")
        g2.bar_chart(pd.Series(calc["settori"]), height=220)
        g3.caption("Per area geografica")
        g3.bar_chart(pd.Series(calc["aree"]), height=220)

    # ── output ──
    st.markdown("#### Output")
    o1, o2 = st.columns(2)
    with o1:
        from core.strategia_pdf import genera_pdf_strategia
        if st.button("Prepara il PDF della strategia", key=f"st_pdf_{pf['id']}", width="stretch"):
            st.session_state[f"st_pdfb_{pf['id']}"] = genera_pdf_strategia(c, pf, calc)
        if st.session_state.get(f"st_pdfb_{pf['id']}"):
            st.download_button("Scarica il PDF", st.session_state[f"st_pdfb_{pf['id']}"], file_name=f"Strategia_{c['nome'].replace(' ', '_')}_{date.today().isoformat()}.pdf",
                               mime="application/pdf", key=f"st_pdfd_{pf['id']}", width="stretch")
    with o2:
        testo = stg.testo_analisi(c, pf, calc)
        st.link_button("Analizza la strategia con Claude", stg.link_claude(testo), width="stretch")
    with st.expander("Testo inviato a Claude (puoi copiarlo in una chat o in un progetto fisso)"):
        st.code(testo, language=None)
        st.download_button("Scarica il testo (.txt)", testo, file_name="analisi_strategia.txt", key=f"st_txt_{pf['id']}")
        st.caption("Il pulsante apre una nuova chat di Claude con il testo già inserito. Se preferisci una chat fissa, crea un Progetto «Analisi strategie» su claude.ai e incolla qui il testo.")

    # ── creazione portafoglio ──
    if not attivo:
        st.markdown("#### Dalla strategia al portafoglio")
        pend = stg.problemi(pf, reg)
        appr = [r for r in pf["righe"] if r.get("stato") == "approvato"]
        st.caption("Metti «Approvato dal cliente» sui prodotti acquistati, aggiorna prezzo, quantità, commissioni e data con i valori reali, poi crea il portafoglio: "
                   "ogni prodotto approvato diventa un acquisto. Gli estratti conto successivi sostituiscono questi valori con quelli ufficiali.")
        manca = [p_ for p_ in pend if any(reg.strumenti[r["strumento"]]["nome"] in p_ for r in appr)]
        for m in manca:
            st.error(m)
        bl = [(reg.strumenti[r["strumento"]]["nome"], t) for r in appr for g, t in __import__("core.completezza", fromlist=["x"]).problemi_strumento(reg.strumenti[r["strumento"]]) if g == "bloccante"]
        for n_, t in bl:
            st.warning(f"{n_}: {t} (completabile anche dopo, ma serve per il report)")
        ok = st.checkbox(f"Confermo: creare il portafoglio con {len(appr)} prodotti approvati", key=f"st_conf_{pf['id']}", disabled=not appr)
        if bottone("Crea il portafoglio", "verde", f"st_crea_{pf['id']}", disabled=not ok or bool(manca)):
            _applica()
            n = stg.crea_portafoglio(c, pf, reg)
            dati.salva_cliente(c)
            st.session_state["cli_msg"] = (f"Portafoglio creato con {n} acquisti. D'ora in poi si aggiorna con gli estratti conto.", [])
            st.rerun()
