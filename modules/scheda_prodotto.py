"""Scheda prodotto: le condizioni della strategia si inseriscono qui, una volta; poi il programma legge solo dati reali."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import dati
from core.completezza import problemi_strumento
from core.config import CATEGORIE, SOTTOCATEGORIE_ALTERNATIVI, SOTTOCATEGORIE_STRUTTURATI, VALUTAZIONE_DEFAULT, VALUTAZIONI

VALUTE = ["CHF", "EUR", "USD", "GBP", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"]
FREQ = {None: "nessuna", 1: "annuale", 2: "semestrale", 4: "trimestrale", 12: "mensile"}


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def mostra_problemi(s: dict):
    pr = problemi_strumento(s)
    if not pr:
        st.success("Scheda completa: tutti i dati necessari al report ci sono.")
        return
    for g, t in pr:
        (st.error if g == "bloccante" else st.warning)(("Da inserire: " if g == "bloccante" else "Consigliato: ") + t)


def campi_prodotto(p: str, s: dict) -> dict:
    """Disegna i campi (dentro un st.form) e restituisce i valori inseriti, da applicare allo strumento."""
    out: dict = {}
    c1, c2, c3 = st.columns([2, 1, 1])
    out["nome"] = c1.text_input("Nome del prodotto", s.get("nome", ""), key=f"{p}_nome")
    cats = list(CATEGORIE)
    out["categoria"] = c2.selectbox("Categoria", cats, index=cats.index(s["categoria"]) if s.get("categoria") in cats else 0, format_func=lambda x: CATEGORIE[x], key=f"{p}_cat")
    out["valuta"] = c3.selectbox("Valuta", VALUTE, index=VALUTE.index(s["valuta"]) if s.get("valuta") in VALUTE else 0, key=f"{p}_val")
    sotto = SOTTOCATEGORIE_STRUTTURATI + SOTTOCATEGORIE_ALTERNATIVI
    c1, c2, c3 = st.columns(3)
    out["sottocategoria"] = c1.selectbox("Tipo (strutturati / alternativi)", [""] + sotto, index=([""] + sotto).index(s["sottocategoria"]) if s.get("sottocategoria") in sotto else 0, key=f"{p}_sub")
    vals = list(VALUTAZIONI)
    cur = s.get("valutazione") or VALUTAZIONE_DEFAULT.get(out["categoria"], "mercato")
    out["valutazione"] = c2.selectbox("Come si valuta", vals, index=vals.index(cur), format_func=lambda x: VALUTAZIONI[x], key=f"{p}_valz",
                                      help="«A scadenza»: si tiene fino al rimborso (costo + cedola maturata). «A mercato»: prezzo di mercato. «NAV manuale»: fondi non quotati.")
    out["isin"] = c3.text_input("ISIN", s.get("isin", ""), key=f"{p}_isin").strip().upper()
    c1, c2, c3 = st.columns(3)
    out["ticker_mercato"] = c1.text_input("Ticker principale (Yahoo)", s.get("ticker_mercato", ""), key=f"{p}_t1", help="Solo per i titoli valutati a mercato. Es. VHYL.L, CS1.PA")
    out["ticker_controllo"] = c2.text_input("Ticker di controllo (Stooq)", s.get("ticker_controllo", ""), key=f"{p}_t2")
    out["prezzo_in_percento"] = c3.checkbox("Prezzo quotato in % del nominale", value=bool(s.get("prezzo_in_percento")), key=f"{p}_pct")
    st.markdown("**Condizioni della strategia**")
    c1, c2, c3 = st.columns(3)
    out["data_emissione"] = c1.date_input("Emissione / inizio", value=_d(s.get("data_emissione")), format="DD.MM.YYYY", key=f"{p}_em")
    out["scadenza"] = c2.date_input("Scadenza", value=_d(s.get("scadenza")), format="DD.MM.YYYY", key=f"{p}_sc")
    freq_keys = list(FREQ)
    out["frequenza_cedola"] = c3.selectbox("Frequenza cedola", freq_keys, index=freq_keys.index(s.get("frequenza_cedola")) if s.get("frequenza_cedola") in freq_keys else 0, format_func=lambda x: FREQ[x], key=f"{p}_fr")
    c1, c2, c3 = st.columns(3)
    out["cedola_annua_pct"] = c1.number_input("Cedola annua %", value=float(s.get("cedola_annua_pct") or 0.0), format="%.4f", key=f"{p}_ced")
    out["barriera_pct"] = c2.number_input("Barriera % del livello iniziale", value=float(s.get("barriera_pct") or 0.0), format="%.2f", key=f"{p}_bar", help="Barriera di sicurezza (es. 60). 0 = nessuna.")
    out["protezione_pct"] = c3.number_input("Capitale protetto %", value=float(s.get("protezione_pct") or 0.0), format="%.2f", key=f"{p}_prot", help="Es. 100 per i certificati a capitale protetto. 0 = nessuna.")
    st.caption("Sottostanti (solo per prodotti con barriera): ticker Yahoo, nome e livello iniziale (il prezzo del sottostante alla data di fissazione iniziale).")
    righe = [{"Ticker": u.get("ticker", ""), "Nome": u.get("nome", ""), "Livello iniziale": u.get("livello_iniziale")} for u in s.get("sottostanti", [])] or [{"Ticker": "", "Nome": "", "Livello iniziale": None}]
    ed = st.data_editor(pd.DataFrame(righe), num_rows="dynamic", hide_index=True, width="stretch", key=f"{p}_sott")
    out["sottostanti"] = [{"ticker": str(r["Ticker"] or "").strip(), "nome": str(r["Nome"] or "").strip() or str(r["Ticker"] or "").strip(),
                           "livello_iniziale": (float(r["Livello iniziale"]) if r["Livello iniziale"] == r["Livello iniziale"] and r["Livello iniziale"] is not None else None)}
                          for r in ed.to_dict("records") if str(r["Ticker"] or "").strip() or str(r["Nome"] or "").strip()]
    if out["valutazione"] == "manuale":
        nav = "\n".join(f"{x['data']};{x['nav']}" for x in s.get("nav_manuale", []))
        out["_nav_testo"] = st.text_area("NAV (una riga: AAAA-MM-GG;valore)", nav, key=f"{p}_nav")
    return out


def applica_campi(s: dict, v: dict):
    s.update(nome=v["nome"].strip() or s.get("nome", ""), categoria=v["categoria"], valuta=v["valuta"], sottocategoria=v["sottocategoria"], valutazione=v["valutazione"],
             ticker_mercato=v["ticker_mercato"].strip(), ticker_controllo=v["ticker_controllo"].strip(), prezzo_in_percento=v["prezzo_in_percento"],
             data_emissione=v["data_emissione"].isoformat() if v["data_emissione"] else "", scadenza=v["scadenza"].isoformat() if v["scadenza"] else "",
             frequenza_cedola=v["frequenza_cedola"], cedola_annua_pct=v["cedola_annua_pct"] or None, barriera_pct=v["barriera_pct"] or None,
             protezione_pct=v["protezione_pct"] or None, sottostanti=v["sottostanti"])
    if v["isin"] and not s.get("isin"):
        s["isin"] = v["isin"]
    if "_nav_testo" in v:
        navs = []
        for r in v["_nav_testo"].splitlines():
            q = [x.strip() for x in r.split(";")]
            if len(q) == 2:
                try:
                    navs.append({"data": q[0], "nav": float(q[1].replace(",", "."))})
                except ValueError:
                    pass
        s["nav_manuale"] = navs
    s["confermato"] = True


def acquisti_registrati(c: dict, k: str):
    tx = [t for t in dati.transazioni_ordinate(c) if t.get("strumento") == k and t["tipo"] in ("acquisto", "vendita", "rimborso")]
    if not tx:
        return
    st.markdown("**Operazioni registrate** (da ricontrollare: quantità, prezzo, importo)")
    st.dataframe(pd.DataFrame([{"Data": t["data"], "Operazione": dati.ETICHETTE_TIPO.get(t["tipo"], t["tipo"]), "Quantità": t.get("quantita"),
                                "Prezzo": (f"{t['prezzo']:g}%" if t.get("prezzo_in_percento") else t.get("prezzo")), "Commissioni": (t.get("commissione") or 0) + (t.get("tasse") or 0),
                                "Importo": t["importo_cassa"], "Valuta": t["valuta"], "Origine": t.get("fonte", "")} for t in tx]), hide_index=True, width="stretch")


def recupera_livelli(reg, k: str, s: dict):
    """Livello iniziale = chiusura del sottostante alla data di fissazione (da Yahoo). Da verificare con la scheda del prodotto."""
    mancanti = [u for u in s.get("sottostanti", []) if u.get("ticker") and not u.get("livello_iniziale")]
    if not mancanti:
        return
    with st.expander("Recupera i livelli iniziali da Yahoo"):
        d = st.date_input("Data di fissazione iniziale (strike date)", value=_d(s.get("data_emissione")) or date.today(), format="DD.MM.YYYY", key=f"sp_{k}_strike")
        if st.button("Recupera livelli mancanti", key=f"sp_{k}_rec"):
            from core.mercato import mercato_reale
            m = mercato_reale()
            ok, ko = [], []
            for u in mancanti:
                v = m.spot(u["ticker"], d.isoformat())
                if v:
                    u["livello_iniziale"] = float(v)
                    ok.append(f"{u['ticker']} {v:,.2f}")
                else:
                    ko.append(u["ticker"])
            dati.salva_registro(reg)
            st.success("Recuperati: " + ", ".join(ok)) if ok else None
            st.warning("Non trovati (inserire a mano): " + ", ".join(ko)) if ko else None
            st.caption("Controlla i valori con il termsheet del prodotto prima di fidarti.")


def scheda(reg, k: str, c: dict | None = None):
    s = reg.strumenti[k]
    mostra_problemi(s)
    if c is not None:
        acquisti_registrati(c, k)
    with st.form(f"sp_form_{k}"):
        v = campi_prodotto(f"sp_{k}", s)
        if st.form_submit_button("Salva scheda", type="primary"):
            applica_campi(s, v)
            dati.salva_registro(reg)
            st.success("Salvato.")
            st.rerun()
    recupera_livelli(reg, k, s)
    st.caption(f"Settori: {s.get('settori') or '—'} · Aree: {s.get('aree') or '—'} · {s.get('classificazione_auto', '')}")
