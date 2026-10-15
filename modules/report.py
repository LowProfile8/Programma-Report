from datetime import date

import pandas as pd
import streamlit as st

from core import dati
from core.config import PERIODI
from core.calcolo import calcola_portafoglio
from core.performance import DatoMancante
from core.report_pdf import genera_pdf
from core.stile import intestazione


def _da(a: date, mesi: int) -> date:
    return (pd.Timestamp(a) - pd.DateOffset(months=mesi)).date()


def _calcola(c, pid, reg, tipo, da, a):
    r = calcola_portafoglio(c, pid, reg, da, a)
    r["tipo"] = tipo
    return r


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
    pfs = dati.assicura_portafogli(c)
    if not pfs:
        st.warning("Questo cliente non ha ancora una strategia: creane una dalla scheda del cliente.")
        return
    pid = st.selectbox("Portafoglio", [p["id"] for p in pfs], format_func=lambda i: next(p["nome"] for p in pfs if p["id"] == i), key="rep_pf")
    pannello(c, reg, dati.portafoglio(c, pid))


def pannello(c, reg, pf):
    """Scelta del periodo, calcolo, controlli e generazione del PDF del report di un portafoglio."""
    pid, c_id = pf["id"], c["id"]
    v = dati.vista_portafoglio(c, pid)
    col1, col2 = st.columns(2)
    tipo = col1.selectbox("Tipo di report", list(PERIODI), key=f"rep_tipo_{pid}")
    a = col2.date_input("Fino al (data di fine periodo)", value=date.today(), key=f"rep_a_{pid}")
    da = _da(a, PERIODI[tipo])
    st.caption(f"Periodo: {da.strftime('%d.%m.%Y')} → {a.strftime('%d.%m.%Y')}")
    if not v.get("transazioni"):
        st.warning("Il cliente non ha ancora movimenti: importa un estratto conto o inserisci le posizioni iniziali.")
        return
    nonconf = [s["nome"] for s in reg.strumenti.values() if not s.get("confermato")]
    if nonconf:
        st.info(f"{len(nonconf)} strumenti non ancora verificati in «Strumenti» (ticker, scadenza, barriera): il report è possibile ma può risultare incompleto.")

    if st.button("Calcola", type="primary", key=f"rep_calcola_{pid}"):
        with st.spinner("Recupero prezzi e cambi, doppio controllo…"):
            try:
                st.session_state[f"rep_stato_{pid}"] = _calcola(c, pid, reg, tipo, da, a)
            except DatoMancante as e:
                st.session_state.pop(f"rep_stato_{pid}", None)
                st.error(f"Dato mancante: {e}. Inserisci il valore a mano qui sotto o correggi lo strumento.")
    S = st.session_state.get(f"rep_stato_{pid}")
    if not S or S["cliente"] != c_id or S.get("portafoglio") != pid:
        return

    ris = S["ris"]
    bloccanti = S["problemi"] or S["incoerenti"]
    from core.completezza import riepilogo_cliente
    schede = riepilogo_cliente(v, reg)
    bl_sch = {k: v for k, v in schede.items() if v["bloccanti"]}
    if schede:
        st.markdown("### Schede prodotto da completare")
        for k, v in schede.items():
            for t_ in v["bloccanti"]:
                st.error(f"{v['nome']}: {t_}")
            for t_ in v["consigliati"]:
                st.warning(f"{v['nome']}: {t_}")
        st.caption("Si completano in Clienti → scheda cliente → Prodotti.")
    if bl_sch:
        if st.checkbox("Genera comunque, anche con schede incomplete", key=f"rep_forza_schede_{pid}"):
            pass
        else:
            bloccanti = True
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
                v = st.number_input("Valore da usare", value=float(p.get("prezzo") or p.get("tasso") or 0.0), format="%.6f", key=f"rep_man_{pid}_{p['chiave']}")
                if st.button("Conferma questo valore", key=f"rep_ok_{pid}_{p['chiave']}"):
                    manuali[p["chiave"]] = v
                    dati.salva_manuali(manuali)
                    st.session_state[f"rep_stato_{pid}"] = _calcola(c, pid, reg, S["tipo"], date.fromisoformat(S["da"]), date.fromisoformat(S["a"]))
                    st.rerun()
    if S["incoerenti"]:
        st.markdown("### Acquisti incoerenti con il mercato")
        st.caption("Il prezzo dell'estratto cade fuori dal range della giornata: controlla ticker, valuta o l'estratto.")
        st.dataframe(pd.DataFrame(S["incoerenti"]), hide_index=True, width="stretch")
        if st.checkbox("Ho verificato: procedi comunque", key=f"rep_forza_{pid}"):
            bloccanti = S["problemi"]

    t = ris["totale"]
    st.markdown("### Anteprima")
    k = st.columns(3)
    k[0].metric("Valore finale", f"{t.get('v1', 0):,.0f}".replace(",", "’") if isinstance(t.get("v1"), (int, float)) else "—")
    for av in ris.get("avvisi", []):
        st.warning(av)
    commento = st.text_area("Commento (facoltativo)", key=f"rep_commento_{pid}", height=140)
    if st.button("Genera PDF", type="primary", disabled=bool(bloccanti), key=f"rep_genera_{pid}"):
        pdf = genera_pdf(ris, c, S["tipo"], commento)
        meta = dati.salva_report({"cliente_id": c["id"], "portafoglio": pid, "cliente": c["nome"], "tipo": S["tipo"], "da": S["da"], "a": S["a"],
                                  "commento": commento, "snapshot": S["snapshot"]}, pdf)
        st.session_state[f"rep_pdf_{pid}"] = (pdf, f"Report_{c['nome'].replace(' ', '_')}_{S['a']}.pdf")
        st.success("Report generato e archiviato.")
    if st.session_state.get(f"rep_pdf_{pid}"):
        pdf, nome = st.session_state[f"rep_pdf_{pid}"]
        st.download_button("Scarica PDF", pdf, file_name=nome, mime="application/pdf")
    if bloccanti:
        st.caption("La generazione è bloccata finché i punti sopra non sono risolti.")
