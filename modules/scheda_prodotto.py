"""Creazione e modifica di un prodotto: prima il tipo, poi solo i campi e le opzioni pertinenti. Settore e area sono facoltativi (se vuoti, classificazione automatica)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import classificatore, dati
from core.anagrafica import nuovo_strumento
from core.completezza import problemi_strumento
from core.config import AREE_GEO, SETTORI, TIPI_PRODOTTO, VALUTAZIONE_DEFAULT, VALUTAZIONI
from core.stile import bottone

VALUTE = ["CHF", "EUR", "USD", "GBP", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"]
FREQ = {None: "nessuna", 1: "annuale", 2: "semestrale", 4: "trimestrale", 12: "mensile"}


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def tipo_di(s: dict) -> str:
    """Etichetta del tipo (Azione, ETF, Obbligazione…) di uno strumento esistente."""
    cat, sotto = s.get("categoria"), s.get("sottocategoria", "")
    if cat == "etf_azioni":
        return "ETF" if sotto.startswith("ETF") or "ETF" in s.get("nome", "").upper() else "Azione"
    for lab, (c, _) in TIPI_PRODOTTO.items():
        if c == cat:
            return lab
    return "Azione"


def mostra_problemi(s: dict):
    pr = problemi_strumento(s)
    if not pr:
        st.success("Scheda completa.")
        return
    for g, t in pr:
        (st.error if g == "bloccante" else st.info)(("Da inserire: " if g == "bloccante" else "Facoltativo: ") + t)


def _num(v):
    return float(v) if v is not None and v == v else None


def campi_prodotto(p: str, s: dict) -> dict:
    """Disegna i campi (senza st.form: i menu dipendenti si aggiornano subito) e restituisce i valori inseriti."""
    out: dict = {}
    tipi = list(TIPI_PRODOTTO)
    t0 = tipo_di(s) if s.get("categoria") else "Azione"
    tipo = st.radio("Che tipo di prodotto è?", tipi, index=tipi.index(t0), horizontal=True, key=f"{p}_tipo")
    cat, sotto_opz = TIPI_PRODOTTO[tipo]
    out["categoria"] = cat
    cur_sub = s.get("sottocategoria") if s.get("sottocategoria") in sotto_opz else sotto_opz[0]
    c1, c2 = st.columns(2)
    out["sottocategoria"] = c1.selectbox("Tipologia", sotto_opz, index=sotto_opz.index(cur_sub), key=f"{p}_sub_{tipo}")
    out["nome"] = c2.text_input("Nome del prodotto", s.get("nome", ""), key=f"{p}_nome")
    c1, c2, c3 = st.columns([1, 1, 1])
    out["valuta"] = c1.selectbox("Valuta", VALUTE, index=VALUTE.index(s["valuta"]) if s.get("valuta") in VALUTE else 0, key=f"{p}_val")
    out["isin"] = c2.text_input("ISIN (facoltativo)", s.get("isin", ""), key=f"{p}_isin").strip().upper()
    pct = cat in ("obbligazione", "strutturato") and out["sottocategoria"] != "Deposito a termine"
    out["prezzo_in_percento"] = pct
    c3.markdown(f"<div style='padding-top:1.9rem;color:#9A9AA2;font-size:0.85rem'>Prezzo: <b style='color:#F2F2F2'>{'in % del nominale' if pct else 'valore per unità'}</b></div>", unsafe_allow_html=True)

    out["ticker_controllo"] = s.get("ticker_controllo", "")
    out["data_emissione"] = _d(s.get("data_emissione"))
    out["scadenza"] = _d(s.get("scadenza"))
    out["frequenza_cedola"] = s.get("frequenza_cedola")
    out["cedola_annua_pct"] = s.get("cedola_annua_pct")
    out["barriera_pct"] = s.get("barriera_pct")
    out["protezione_pct"] = s.get("protezione_pct")
    out["sottostanti"] = s.get("sottostanti", [])
    out["ticker_mercato"] = s.get("ticker_mercato", "")
    out["strike"] = s.get("strike")

    if cat in ("etf_azioni", "opzione") or out["sottocategoria"] == "Criptovaluta":
        out["ticker_mercato"] = st.text_input("Ticker per il prezzo (Yahoo Finance)", s.get("ticker_mercato", ""), key=f"{p}_t1",
                                              help="Es. VHYL.L, CS1.PA, NESN.SW, BTC-USD. Per le opzioni: ticker del contratto, se disponibile.")
    if cat == "obbligazione" and out["sottocategoria"] != "Deposito a termine":
        out["ticker_mercato"] = st.text_input("Ticker Yahoo (facoltativo: per il prezzo automatico; altrimenti lo aggiorni tu a mano)", s.get("ticker_mercato", ""), key=f"{p}_t1o")
    if cat == "opzione":
        c1, c2 = st.columns(2)
        out["strike"] = c1.number_input("Strike", value=float(s.get("strike") or 0.0), format="%.4f", key=f"{p}_strike")
        out["scadenza"] = c2.date_input("Scadenza dell'opzione", value=_d(s.get("scadenza")), format="DD.MM.YYYY", key=f"{p}_sc")
    if cat in ("obbligazione", "strutturato"):
        c1, c2 = st.columns(2)
        out["data_emissione"] = c1.date_input("Emissione / data di fissazione", value=_d(s.get("data_emissione")), format="DD.MM.YYYY", key=f"{p}_em")
        out["scadenza"] = c2.date_input("Scadenza / rimborso", value=_d(s.get("scadenza")), format="DD.MM.YYYY", key=f"{p}_sc")
        c1, c2 = st.columns(2)
        out["cedola_annua_pct"] = c1.number_input("Cedola annua %", value=float(s.get("cedola_annua_pct") or 0.0), format="%.4f", key=f"{p}_ced") or None
        fk = list(FREQ)
        out["frequenza_cedola"] = c2.selectbox("Frequenza cedola", fk, index=fk.index(s.get("frequenza_cedola")) if s.get("frequenza_cedola") in fk else 0,
                                               format_func=lambda x: FREQ[x], key=f"{p}_fr")
    if cat == "strutturato":
        c1, c2 = st.columns(2)
        out["barriera_pct"] = c1.number_input("Barriera % del livello iniziale (0 = nessuna)", value=float(s.get("barriera_pct") or 0.0), format="%.2f", key=f"{p}_bar") or None
        out["protezione_pct"] = c2.number_input("Capitale protetto % (0 = nessuna)", value=float(s.get("protezione_pct") or 0.0), format="%.2f", key=f"{p}_prot") or None
        st.caption("Sottostanti: ticker Yahoo (es. ^GSPC, ^STOXX50E, ^SSMI, AAPL), nome e livello iniziale alla data di fissazione.")
        righe = [{"Ticker": u.get("ticker", ""), "Nome": u.get("nome", ""), "Livello iniziale": u.get("livello_iniziale")} for u in s.get("sottostanti", [])] or [{"Ticker": "", "Nome": "", "Livello iniziale": None}]
        ed = st.data_editor(pd.DataFrame(righe), num_rows="dynamic", hide_index=True, width="stretch", key=f"{p}_sott")
        out["sottostanti"] = [{"ticker": str(r["Ticker"] or "").strip(), "nome": str(r["Nome"] or "").strip() or str(r["Ticker"] or "").strip(), "livello_iniziale": _num(r["Livello iniziale"])}
                              for r in ed.to_dict("records") if str(r["Ticker"] or "").strip() or str(r["Nome"] or "").strip()]
    if cat == "alternativo" and out["sottocategoria"] != "Criptovaluta":
        nav = "\n".join(f"{x['data']};{x['nav']}" for x in s.get("nav_manuale", []))
        out["_nav_testo"] = st.text_area("Valore (NAV) – una riga per data: AAAA-MM-GG;valore", nav, key=f"{p}_nav", height=90)

    st.markdown("**Settore e area geografica** (facoltativi: se li lasci vuoti li ricavo io)")
    c1, c2 = st.columns(2)
    set_corr = [k for k in (s.get("settori") or {}) if s.get("classificazione_manuale")]
    are_corr = [k for k in (s.get("aree") or {}) if s.get("classificazione_manuale")]
    out["_settori"] = c1.multiselect("Settore", sorted(set(SETTORI) | set(set_corr)), default=set_corr, key=f"{p}_set", placeholder="Automatico")
    out["_aree"] = c2.multiselect("Area geografica", sorted(set(AREE_GEO) | set(are_corr)), default=are_corr, key=f"{p}_are", placeholder="Automatica")

    # valutazione di default coerente con il tipo
    if out["sottocategoria"] == "Criptovaluta":
        val_def = "mercato"
    elif cat == "obbligazione" and out["ticker_mercato"].strip():
        val_def = "mercato"
    elif out["sottocategoria"] == "Deposito a termine":
        val_def = "scadenza"
    else:
        val_def = VALUTAZIONE_DEFAULT.get(cat, "mercato")
    with st.expander("Opzioni avanzate"):
        vals = list(VALUTAZIONI)
        cur = s.get("valutazione") or val_def
        out["valutazione"] = st.selectbox("Come si valuta nel report", vals, index=vals.index(cur if cur in vals else val_def), format_func=lambda x: VALUTAZIONI[x], key=f"{p}_valz_{cat}_{out['sottocategoria']}_{val_def}",
                                          help="Strutturati: sempre al 100% del nominale, con le cedole incassate nella performance. Obbligazioni: prezzo in % (da Yahoo o inserito a mano). Azioni/ETF: prezzo di mercato.")
        out["ticker_controllo"] = st.text_input("Ticker di controllo (Stooq) – seconda fonte", s.get("ticker_controllo", ""), key=f"{p}_t2")
        if cat not in ("etf_azioni", "opzione") and out["sottocategoria"] != "Criptovaluta":
            out["ticker_mercato"] = st.text_input("Ticker di mercato (solo se valutato a mercato)", s.get("ticker_mercato", ""), key=f"{p}_t1b")
    return out


def applica_campi(s: dict, v: dict):
    iso = lambda d: d.isoformat() if d else ""
    s.update(nome=v["nome"].strip() or s.get("nome", ""), categoria=v["categoria"], valuta=v["valuta"], sottocategoria=v["sottocategoria"], valutazione=v["valutazione"],
             ticker_mercato=v["ticker_mercato"].strip(), ticker_controllo=v["ticker_controllo"].strip(), prezzo_in_percento=v["prezzo_in_percento"],
             data_emissione=iso(v["data_emissione"]), scadenza=iso(v["scadenza"]), frequenza_cedola=v["frequenza_cedola"], cedola_annua_pct=v["cedola_annua_pct"] or None,
             barriera_pct=v["barriera_pct"] or None, protezione_pct=v["protezione_pct"] or None, sottostanti=v["sottostanti"])
    if v.get("strike"):
        s["strike"] = v["strike"]
    if v["isin"]:
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
    # classificazione: scelta manuale (pesi uguali) oppure automatica
    if v["_settori"] or v["_aree"]:
        auto = classificatore.classifica(s, None)
        s["settori"] = {k: 1.0 / len(v["_settori"]) for k in v["_settori"]} if v["_settori"] else (auto["settori"] or s.get("settori", {}))
        s["aree"] = {k: 1.0 / len(v["_aree"]) for k in v["_aree"]} if v["_aree"] else (auto["aree"] or s.get("aree", {}))
        s["classificazione_manuale"] = True
        s["classificazione_auto"] = "scelta manuale"
    else:
        if s.get("classificazione_manuale"):
            s["classificazione_manuale"] = False
            s["settori"], s["aree"] = {}, {}
        classificatore.applica(s, None)
    s["confermato"] = True


def crea_prodotto(reg, v: dict) -> str:
    sim = "" if v["isin"] else "MAN" + dati.db.nuovo_id()[:8].upper()
    k = reg.assicura(v["isin"], sim, v["nome"].strip(), v["valuta"], v["prezzo_in_percento"])
    applica_campi(reg.strumenti[k], v)
    return k


def nuovo(reg, prefisso: str = "np") -> str | None:
    """Crea un prodotto nuovo e ne restituisce la chiave (o None)."""
    v = campi_prodotto(prefisso, {})
    if bottone("Crea prodotto", "verde", f"{prefisso}_crea"):
        if not v["nome"].strip():
            st.error("Serve almeno il nome del prodotto.")
            return None
        k = crea_prodotto(reg, v)
        dati.salva_registro(reg)
        return k
    return None


def acquisti_registrati(c: dict, k: str):
    tx = [t for t in dati.transazioni_ordinate(c) if t.get("strumento") == k and t["tipo"] in ("acquisto", "vendita", "rimborso")]
    if not tx:
        return
    st.markdown("**Operazioni registrate** (da ricontrollare: quantità, prezzo, importo)")
    st.dataframe(pd.DataFrame([{"Data": t["data"], "Operazione": dati.ETICHETTE_TIPO.get(t["tipo"], t["tipo"]), "Quantità": t.get("quantita"),
                                "Prezzo": (f"{t['prezzo']:g}%" if t.get("prezzo_in_percento") else t.get("prezzo")), "Commissioni": (t.get("commissione") or 0) + (t.get("tasse") or 0),
                                "Importo": t["importo_cassa"], "Valuta": t["valuta"], "Origine": t.get("fonte", "")} for t in tx]), hide_index=True, width="stretch")


def recupera_livelli(reg, k: str, s: dict, ctx: str = "g"):
    """Livello iniziale = chiusura del sottostante alla data di fissazione (da Yahoo). Da verificare con la scheda del prodotto."""
    mancanti = [u for u in s.get("sottostanti", []) if u.get("ticker") and not u.get("livello_iniziale")]
    if not mancanti:
        return
    with st.expander("Recupera i livelli iniziali da Yahoo"):
        d = st.date_input("Data di fissazione iniziale (strike date)", value=_d(s.get("data_emissione")) or date.today(), format="DD.MM.YYYY", key=f"sp{ctx}_{k}_strike")
        if st.button("Recupera livelli mancanti", key=f"sp{ctx}_{k}_rec"):
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
            if ok:
                st.success("Recuperati: " + ", ".join(ok))
            if ko:
                st.warning("Non trovati (inserire a mano): " + ", ".join(ko))
            st.caption("Controlla i valori con il termsheet del prodotto prima di fidarti.")


def scheda(reg, k: str, c: dict | None = None, ctx: str = "g"):
    s = reg.strumenti[k]
    mostra_problemi(s)
    if c is not None:
        acquisti_registrati(c, k)
    v = campi_prodotto(f"sp{ctx}_{k}", s)
    if bottone("Salva scheda", "verde", f"sp{ctx}_{k}_salva"):
        applica_campi(s, v)
        dati.salva_registro(reg)
        st.success("Salvato.")
        st.rerun()
    recupera_livelli(reg, k, s, ctx)
    st.caption(f"Settori: {s.get('settori') or '—'} · Aree: {s.get('aree') or '—'} · {s.get('classificazione_auto', '')}")
