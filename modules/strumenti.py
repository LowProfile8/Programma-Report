import streamlit as st

from core import dati
from core.config import CATEGORIE, SOTTOCATEGORIE_ALTERNATIVI, SOTTOCATEGORIE_STRUTTURATI, VALUTAZIONI
from core.stile import intestazione


def _scheda(k, s, reg):
    with st.form(f"str_f_{k}"):
        s["nome"] = st.text_input("Nome", s.get("nome", ""))
        c1, c2, c3 = st.columns(3)
        cats = list(CATEGORIE)
        s["categoria"] = c1.selectbox("Categoria", cats, index=cats.index(s["categoria"]) if s["categoria"] in cats else 0, format_func=lambda x: CATEGORIES_LABEL(x))
        vals = list(VALUTAZIONI)
        s["valutazione"] = c2.selectbox("Valutazione", vals, index=vals.index(s["valutazione"]), format_func=lambda x: VALUTAZIONI[x])
        s["valuta"] = c3.text_input("Valuta", s.get("valuta", ""))
        if s["categoria"] == "strutturato":
            s["sottocategoria"] = st.selectbox("Tipo", SOTTOCATEGORIE_STRUTTURATI, index=SOTTOCATEGORIE_STRUTTURATI.index(s["sottocategoria"]) if s.get("sottocategoria") in SOTTOCATEGORIE_STRUTTURATI else 0)
        elif s["categoria"] == "alternativo":
            s["sottocategoria"] = st.selectbox("Tipo", SOTTOCATEGORIE_ALTERNATIVI, index=SOTTOCATEGORIE_ALTERNATIVI.index(s["sottocategoria"]) if s.get("sottocategoria") in SOTTOCATEGORIE_ALTERNATIVI else 0)
        t1, t2 = st.columns(2)
        s["ticker_mercato"] = t1.text_input("Ticker principale (Yahoo)", s.get("ticker_mercato", ""))
        s["ticker_controllo"] = t2.text_input("Ticker di controllo (Stooq)", s.get("ticker_controllo", ""))
        d1, d2, d3 = st.columns(3)
        s["scadenza"] = d1.text_input("Scadenza (AAAA-MM-GG)", s.get("scadenza", ""))
        s["data_emissione"] = d2.text_input("Emissione (AAAA-MM-GG)", s.get("data_emissione", ""))
        ced = d3.number_input("Cedola annua %", value=float(s.get("cedola_annua_pct") or 0.0), format="%.3f")
        s["cedola_annua_pct"] = ced or None
        e1, e2 = st.columns(2)
        s["frequenza_cedola"] = int(e1.selectbox("Cedole all'anno", [1, 2, 4, 12], index=[1, 2, 4, 12].index(s["frequenza_cedola"]) if s.get("frequenza_cedola") in (1, 2, 4, 12) else 1))
        bar = e2.number_input("Barriera % del livello iniziale", value=float(s.get("barriera_pct") or 0.0), format="%.2f")
        s["barriera_pct"] = bar or None
        if s["categoria"] == "strutturato":
            testo = "\n".join(f"{u.get('ticker','')};{u.get('nome','')};{u.get('livello_iniziale','')}" for u in s.get("sottostanti", []))
            nuovo = st.text_area("Sottostanti (una riga: ticker;nome;livello iniziale)", testo)
        if s["valutazione"] == "manuale":
            nav = "\n".join(f"{x['data']};{x['nav']}" for x in s.get("nav_manuale", []))
            nav_t = st.text_area("NAV manuali (una riga: AAAA-MM-GG;valore)", nav)
        if st.form_submit_button("Salva", type="primary"):
            if s["categoria"] == "strutturato":
                out = []
                for r in nuovo.splitlines():
                    p = [x.strip() for x in r.split(";")]
                    if p and p[0]:
                        try:
                            lv = float(p[2].replace(",", ".")) if len(p) > 2 and p[2] else None
                        except ValueError:
                            lv = None
                        out.append({"ticker": p[0], "nome": p[1] if len(p) > 1 else p[0], "livello_iniziale": lv})
                s["sottostanti"] = out
            if s["valutazione"] == "manuale":
                navs = []
                for r in nav_t.splitlines():
                    p = [x.strip() for x in r.split(";")]
                    if len(p) == 2:
                        try:
                            navs.append({"data": p[0], "nav": float(p[1].replace(",", "."))})
                        except ValueError:
                            pass
                s["nav_manuale"] = navs
            s["confermato"] = True
            dati.salva_registro(reg)
            st.success("Salvato.")
    st.caption(f"Settori: {s.get('settori') or '—'} · Aree: {s.get('aree') or '—'} · {s.get('classificazione_auto', '')}")


def CATEGORIES_LABEL(x):
    return CATEGORIE.get(x, x)


def render():
    intestazione("Strumenti", "Anagrafica comune a tutti i clienti. Controlla gli strumenti nuovi: ticker, scadenza, barriera.")
    reg = dati.carica_registro()
    if not reg.strumenti:
        st.info("Nessuno strumento: si creano da soli importando un estratto conto.")
        return
    solo = st.checkbox("Mostra solo da verificare", value=True, key="str_solo")
    for k, s in sorted(reg.strumenti.items(), key=lambda x: x[1].get("nome", "")):
        if solo and s.get("confermato"):
            continue
        stato = "✓" if s.get("confermato") else "da verificare"
        with st.expander(f"{s.get('nome') or k} — {CATEGORIE.get(s['categoria'], '')} · {stato}"):
            _scheda(k, s, reg)
