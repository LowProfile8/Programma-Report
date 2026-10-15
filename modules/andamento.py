"""Andamento in tempo reale del portafoglio: valore, performance, scadenze, cedole, esposizioni, costi."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core import dati
from core.calcolo import calcola_portafoglio
from core.config import CATEGORIE
from core.performance import DatoMancante


def _e(x, d=0):
    return "–" if x is None else f"{x:,.{d}f}".replace(",", "’")


def _p(x, d=2):
    return "n.d." if x is None else f"{100 * x:+.{d}f}%"


def render(c, reg, pf):
    v = dati.vista_portafoglio(c, pf["id"])
    tx = dati.transazioni_ordinate(v)
    if not tx:
        st.info("Nessun movimento in questo portafoglio: crea il portafoglio dalla strategia o importa un estratto conto.")
        return
    oggi = date.today()
    inizio = date.fromisoformat(tx[0]["data"]) - timedelta(days=1)
    chiave = f"and_{pf['id']}"
    premuto = st.button("Calcola l'andamento con i prezzi di oggi" if chiave not in st.session_state else "Aggiorna con i prezzi di oggi", key=f"{chiave}_btn", type="primary")
    if chiave not in st.session_state and not premuto:
        st.caption("Il calcolo usa i prezzi di mercato di oggi (due fonti a confronto): parte quando premi il pulsante.")
        return
    if premuto:
        try:
            st.session_state[chiave] = calcola_portafoglio(c, pf["id"], reg, inizio, oggi)
        except DatoMancante as e:
            st.session_state.pop(chiave, None)
            st.error(f"Dato mancante: {e}. Se è un prezzo, completa la scheda del prodotto (ticker, NAV) in «Prodotti»; se è un cambio o la fonte non risponde, riprova più tardi.")
            return
        except Exception as e:  # rete o fonte di prezzo non raggiungibile
            st.session_state.pop(chiave, None)
            st.error(f"Non riesco a calcolare l'andamento ({e}). Riprova fra poco.")
            return
    S = st.session_state[chiave]
    ris, base = S["ris"], S["ris"]["periodo"]["base"]
    t = ris["totale"]
    for p in S["problemi"]:
        st.warning(f"Prezzo da verificare: {p.get('chiave')} — {str(p.get('stato', '')).replace('_', ' ')}")
    k = st.columns(4)
    k[0].metric("Valore del portafoglio", f"{base} {_e(ris['valore_portafoglio'])}")
    k[1].metric("Proventi incassati", f"{base} {_e(sum(p['importo_base'] for p in ris['proventi']))}")
    k[2].metric("Performance dall'inizio", _p(t.get("rendimento_dall_inizio")))
    k[3].metric("Annualizzata (XIRR)", _p(t.get("xirr")) if t.get("xirr") is not None else "–")

    st.markdown("#### Prodotti attivi e scadenze")
    att = ris["attivi"]
    if att:
        righe = []
        for r in att:
            gg = (date.fromisoformat(r["scadenza"]) - oggi).days if r.get("scadenza") else None
            tot_gg = (date.fromisoformat(r["scadenza"]) - date.fromisoformat(r["apertura"])).days if r.get("scadenza") and r.get("apertura") else None
            avanz = max(0.0, min(1.0, 1 - gg / tot_gg)) if gg is not None and tot_gg else None
            righe.append({"Prodotto": r["nome"], "Acquisto": r["apertura"], "Scadenza": r["scadenza"] or "–", "Giorni alla scadenza": gg, "Avanzamento": avanz,
                          f"Investito ({base})": r["investito"], f"Valore ({base})": r["valore"], "Proventi": r["redditi"], "Rendimento": r["rendimento"]})
        st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch", column_config={
            "Avanzamento": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="percent"),
            "Rendimento": st.column_config.NumberColumn(format="percent"),
            f"Investito ({base})": st.column_config.NumberColumn(format="%.0f"), f"Valore ({base})": st.column_config.NumberColumn(format="%.0f"),
            "Proventi": st.column_config.NumberColumn(format="%.0f")})
    else:
        st.caption("Nessun prodotto attivo.")
    barr = [b for b in ris["barriere"] if b.get("completo")]
    if barr:
        nomi = {r["chiave"]: r["nome"] for r in ris["attivi"]}
        pal = {"verde": "🟢 ampia", "giallo": "🟡 da seguire", "rosso": "🔴 ridotta"}
        st.markdown("**Distanza dalla barriera**")
        st.dataframe(pd.DataFrame([{"Prodotto": nomi.get(b["chiave"], b["chiave"]), "Distanza": f"{100 * b['buffer']:.0f}%", "Giudizio": pal[b["semaforo"]]} for b in barr]), hide_index=True, width="stretch")

    g1, g2 = st.columns(2)
    g1.markdown("**Per tipo di investimento**")
    g1.bar_chart(pd.Series({CATEGORIE.get(k_, k_): v for k_, v in ris["allocazione"].items() if v > 0}))
    g2.markdown("**Per valuta**")
    g2.bar_chart(pd.Series({k_: v for k_, v in ris["valute"].items() if v > 0}))
    g3, g4 = st.columns(2)
    g3.markdown("**Per settore**")
    g3.bar_chart(pd.Series({k_: v for k_, v in ris["settori"].items() if v > 0}))
    g4.markdown("**Per area geografica**")
    g4.bar_chart(pd.Series({k_: v for k_, v in ris["aree"].items() if v > 0}))

    pr = ris["proventi"]
    if pr:
        st.markdown("#### Cedole e proventi incassati")
        df = pd.DataFrame(pr)
        df["mese"] = df["data"].str[:7]
        st.bar_chart(df.groupby("mese")["importo_base"].sum())
        with st.expander("Dettaglio"):
            st.dataframe(df[["data", "nome", "tipo", "valuta", "importo", "importo_base"]], hide_index=True, width="stretch")
    fut = ris["cedole_future"]
    if fut:
        st.markdown("#### Prossime cedole attese")
        st.dataframe(pd.DataFrame(fut)[["data", "nome", "valuta", "importo", "importo_base"]].head(24), hide_index=True, width="stretch")
    cd = ris["costi_dettaglio"]
    with st.expander("Costi e riconciliazione dei movimenti"):
        st.write(f"Commissioni {_e(cd['commissioni'], 2)} · custodia {_e(cd['custodia'], 2)} · spese {_e(cd['spese'], 2)} · imposte {_e(cd['imposte'], 2)} · **totale {_e(cd['totale'], 2)} {base}**")
        rc = ris["riconciliazione"]
        from core.riepiloghi import GRUPPI
        st.dataframe(pd.DataFrame([{"Voce": e_, "N.": rc["righe"][k_]["n"], f"Effetto ({base})": rc["righe"][k_]["base"]} for k_, e_ in GRUPPI if rc["righe"][k_]["n"]]), hide_index=True, width="stretch")
    for a in ris.get("avvisi", []):
        st.warning(a)
