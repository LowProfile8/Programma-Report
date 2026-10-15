"""PDF della proposta di strategia da presentare al cliente (sfondo chiaro, stessa grafica del report)."""

from __future__ import annotations

import io
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Spacer, Table, TableStyle

from core.config import ASSET, CATEGORIE, NOME_STUDIO
from core.report_pdf import GRIGIO, NERO, P, _img, _kpi, barre, dt, n, pct, tabella, torta, colors

DISCLAIMER_STRATEGIA = (
    "Questa è una proposta di strategia di investimento a scopo informativo, non un'offerta vincolante né una consulenza legale o fiscale. "
    "Prezzi, quantità e importi sono indicativi: all'acquisto possono differire. Le cedole indicate sono quelle previste dalle condizioni dei prodotti "
    "e dipendono, per i prodotti strutturati, dall'andamento dei sottostanti e dalla solvibilità dell'emittente. Il valore degli investimenti può scendere come salire; "
    "i rendimenti passati non sono indicativi di quelli futuri."
)


def _riga2(sx, dx, wx=84, wd=90):
    t = Table([[sx, dx]], colWidths=[wx * mm, wd * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    return t


def genera_pdf_strategia(cliente: dict, pf: dict, calc: dict) -> bytes:
    base = pf["valuta"]
    tot = calc["totale"] or 1.0
    buf = io.BytesIO()
    larg, alt = A4
    logo = ASSET / "logo_pdf.png"
    from PIL import Image as PILImage
    lw0, lh0 = PILImage.open(logo).size
    titolo = "PROPOSTA DI STRATEGIA"
    oggi = date.today().strftime("%d.%m.%Y")

    def testata(canvas, doc, grande):
        canvas.saveState()
        lw = 52 * mm if grande else 34 * mm
        canvas.drawImage(str(logo), 18 * mm, alt - (14 * mm if grande else 11 * mm) - lw * lh0 / lw0, width=lw, height=lw * lh0 / lw0, mask="auto")
        canvas.setFillColor(NERO)
        if grande:
            canvas.setFont("Helvetica", 8.5); canvas.drawRightString(larg - 18 * mm, alt - 17 * mm, f"Sig. {cliente['nome']}")
            canvas.setFont("Helvetica-Bold", 11.5); canvas.drawRightString(larg - 18 * mm, alt - 22.5 * mm, titolo)
            canvas.setFont("Helvetica-Bold", 8.5); canvas.drawRightString(larg - 18 * mm, alt - 27.5 * mm, f"{pf['nome']} · {oggi}")
        else:
            canvas.setFont("Helvetica", 7.5); canvas.drawRightString(larg - 18 * mm, alt - 14 * mm, f"Sig. {cliente['nome']} · {titolo.title()} · {oggi}")
        canvas.setStrokeColor(colors.HexColor("#BBBBBB")); canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 15 * mm, larg - 18 * mm, 15 * mm)
        canvas.setFont("Helvetica", 6.5); canvas.setFillColor(GRIGIO)
        canvas.drawString(18 * mm, 11 * mm, f"{NOME_STUDIO} · Bissone (TI)")
        canvas.drawRightString(larg - 18 * mm, 11 * mm, f"Pagina {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=36 * mm, bottomMargin=20 * mm,
                          title=f"{titolo} – {cliente['nome']}", author=NOME_STUDIO)
    f1 = Frame(18 * mm, 20 * mm, larg - 36 * mm, alt - 70 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="f1")
    f2 = Frame(18 * mm, 20 * mm, larg - 36 * mm, alt - 48 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="f2")
    doc.addPageTemplates([PageTemplate(id="prima", frames=[f1], onPage=lambda c, d: testata(c, d, True), autoNextPageTemplate="altre"),
                          PageTemplate(id="altre", frames=[f2], onPage=lambda c, d: testata(c, d, False))])

    el = []
    rend = calc["rendimento_cedolare"]
    el.append(_kpi([
        ("Capitale da investire", f"{base} {n(pf['capitale'], 0)}", f"profilo di rischio {cliente.get('rischio', '-')} su 5"),
        ("Prodotti proposti", str(len(calc["righe"])), "vedi elenco a pagina 3"),
        ("Reddito annuo atteso", f"{base} {n(calc['reddito_annuo'], 0)}", f"{pct(rend, 1)} del capitale investito" if rend else "cedole e proventi previsti"),
        ("Liquidità residua", f"{base} {n(max(calc['liquidita_residua'], 0), 0)}", "non investita"),
    ]))
    el.append(Spacer(1, 8))
    el.append(P("COME PROPONIAMO DI INVESTIRE", "titolo"))
    for titolo_t, dati_, etich in (("Per tipo di investimento", calc["allocazione"], CATEGORIE), ("Per valuta", calc["valute"], {})):
        righe = [[etich.get(k, k), n(v, 0), pct(v / tot, 1)] for k, v in sorted(dati_.items(), key=lambda kv: -kv[1]) if v > 0]
        righe.append(["Totale", n(sum(dati_.values()), 0), "100,0%"])
        t = tabella([titolo_t, f"Importo ({base})", "%"], righe, [38, 26, 14], extra=[("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("LINEABOVE", (0, -1), (-1, -1), 0.6, NERO)])
        el.append(_riga2(t, _img(torta(dati_, etich), 70)))
    el.append(Spacer(1, 6))
    el.append(KeepTogether([P("L'IDEA DELLA STRATEGIA", "titolo"), P(
        "I prodotti sono scelti per bilanciare reddito periodico (cedole, interessi, dividendi) e crescita, in linea con il profilo di rischio del cliente. "
        "Le pagine seguenti mostrano in quali settori e aree geografiche si investe e l'elenco dei prodotti consigliati.", "testo")]))

    el.append(PageBreak())
    el.append(P("DOVE INVESTIAMO", "titolo"))
    sett = {k: v for k, v in calc["settori"].items() if v > 0}
    aree = {k: v for k, v in calc["aree"].items() if v > 0}
    el.append(_riga2([P("Per settore", "sotto"), _img(barre(sett), 82)], [P("Per area geografica", "sotto"), _img(barre(aree), 82)], 87, 87))
    el.append(P("Le esposizioni sono calcolate sul controvalore dei prodotti. Per ETF e indici si usa la composizione di riferimento: i valori sono indicativi.", "piccolo"))
    red = {x["nome"]: x["importo_base"] * (x["cedola_annua_pct"] or 0) / 100 if not x["prezzo_in_percento"] else x["quantita"] * x["tasso"] * (x["cedola_annua_pct"] or 0) / 100
           for x in calc["righe"] if x.get("cedola_annua_pct")}
    if red:
        el.append(KeepTogether([P("DA DOVE ARRIVA IL REDDITO ATTESO", "titolo"), _img(barre(red), 120),
                                P(f"Quota del reddito annuo atteso di {base} {n(calc['reddito_annuo'], 0)}, secondo le cedole previste dai prodotti. Non è una garanzia.", "piccolo")]))
    scad = sorted([x for x in calc["righe"] if x.get("scadenza")], key=lambda x: x["scadenza"])
    if scad:
        el.append(KeepTogether([P("LE SCADENZE", "titolo"), tabella(["Prodotto", "Scadenza", f"Importo ({base})"], [[P(x["nome"]), dt(x["scadenza"]), n(x["importo_base"], 0)] for x in scad], [100, 28, 30])]))

    el.append(PageBreak())
    el.append(P("I PRODOTTI CHE CONSIGLIAMO DI ACQUISTARE", "titolo"))
    righe = []
    for x in calc["righe"]:
        det = [CATEGORIE.get(x["categoria"], "")] + ([x["sottocategoria"]] if x["sottocategoria"] else []) + ([x["isin"]] if x["isin"] else [])
        nome = f"{x['nome']}<br/><font size=6 color='#666666'>{' · '.join(det)}</font>"
        cond = []
        if x.get("cedola_annua_pct"): cond.append(f"cedola {n(x['cedola_annua_pct'], 2)}%")
        if x.get("barriera_pct"): cond.append(f"barriera {n(x['barriera_pct'], 0)}%")
        if x.get("protezione_pct"): cond.append(f"protezione {n(x['protezione_pct'], 0)}%")
        prezzo = f"{n(x['prezzo'], 2)}%" if x["prezzo_in_percento"] else n(x["prezzo"], 2)
        righe.append([P(nome), pct(x["peso_eff_pct"] / 100, 1), f"{x['valuta']} {prezzo}", n(x["quantita"], 0), n(x["importo_base"], 0), P("<br/>".join(cond) or "–"), dt(x["scadenza"]) if x["scadenza"] else "–"])
    righe.append([P("<b>Totale</b>"), "100,0%", "", "", n(calc["totale"], 0), "", ""])
    el.append(tabella(["Prodotto", "Peso", "Prezzo indicativo", "Quantità / nominale", f"Importo ({base})", "Condizioni", "Scadenza"], righe, [58, 12, 24, 20, 22, 26, 18],
                      allinea_destra_da=1, extra=[("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("LINEABOVE", (0, -1), (-1, -1), 0.6, NERO), ("ALIGN", (5, 0), (5, -1), "LEFT")]))
    el.append(P("Prezzi e quantità sono quelli ideali alla data di preparazione e possono variare all'esecuzione. Per obbligazioni e prodotti strutturati il prezzo è espresso in % del nominale.", "piccolo"))
    el.append(Spacer(1, 10))
    el.append(P("NOTE", "titolo"))
    el.append(P(DISCLAIMER_STRATEGIA, "piccolo"))
    doc.build(el)
    return buf.getvalue()
