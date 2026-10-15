"""Costanti dell'applicazione."""

from pathlib import Path

NOME_STUDIO = "Athena Advisory Group"
TITOLO_PAGINA = "Athena — report finanziari"
RADICE = Path(__file__).resolve().parent.parent
ASSET = RADICE / "assets"
DATI_LOCALI = RADICE / "dati_locali"          # usata solo se Supabase non è collegato
CACHE_PREZZI = DATI_LOCALI / "cache_prezzi.json"

VALUTE_BASE = ["CHF", "EUR", "USD"]
PERIODI = {"Trimestrale": 3, "Semestrale": 6, "Annuale": 12}

# Categorie di strumento (macro) e relative sotto-categorie
CATEGORIE = {
    "liquidita": "Liquidità",
    "obbligazione": "Obbligazioni",
    "etf_azioni": "Azioni / ETF",
    "opzione": "Opzioni",
    "strutturato": "Prodotti strutturati",
    "alternativo": "Investimenti alternativi",
}
SOTTOCATEGORIE_STRUTTURATI = [
    "Barrier Reverse Convertible", "Capital Protection Note", "Bullish Shark Note",
    "Bearish Shark Note", "Airbag Certificate", "Altro strutturato",
]
SOTTOCATEGORIE_ALTERNATIVI = ["Fondo immobiliare", "Private equity", "Hedge fund", "Criptovaluta", "Altro alternativo"]
SOTTOCATEGORIE_STRUTTURATI += ["Autocallable", "Bonus Certificate", "Discount Certificate", "Tracker / Participation"]

# Scelta guidata alla creazione di un prodotto: prima il tipo, poi il menu a tendina dei soli sottotipi pertinenti.
# etichetta -> (categoria interna, sottotipi)
TIPI_PRODOTTO = {
    "Azione": ("etf_azioni", ["Azione ordinaria", "Azione estera / ADR"]),
    "ETF": ("etf_azioni", ["ETF azionario", "ETF obbligazionario", "ETF materie prime", "ETF multi-asset", "ETF tematico"]),
    "Obbligazione": ("obbligazione", ["Governativa", "Corporate", "Convertibile", "Subordinata", "Deposito a termine", "Altra obbligazione"]),
    "Opzione": ("opzione", ["Call acquistata", "Put acquistata", "Call venduta (covered call)", "Put venduta (cash secured)", "Altra opzione"]),
    "Prodotto strutturato": ("strutturato", [x for x in SOTTOCATEGORIE_STRUTTURATI]),
    "Alternativo": ("alternativo", ["Fondo immobiliare", "Private equity", "Hedge fund", "Criptovaluta", "Altro alternativo"]),
}
SETTORI = ["Tecnologia", "Healthcare", "Finanziario", "Industriale", "Consumi discrezionali", "Consumi di base", "Energia", "Servizi di pubblica utilità",
           "Materie prime", "Immobiliare", "Comunicazione", "Governativo", "Diversificato", "Altri settori"]
AREE_GEO = ["Stati Uniti", "Europa", "Svizzera", "Asia", "Mercati emergenti", "Altro"]

# Come si valuta uno strumento nel report
#   mercato  -> quantità x prezzo di mercato
#   scadenza -> al costo (+ cedole): si porta a scadenza, le oscillazioni non contano
#   manuale  -> ultimo NAV inserito a mano (fondi non quotati)
VALUTAZIONI = {"mercato": "A mercato", "scadenza": "A scadenza (al costo)", "manuale": "NAV manuale"}
VALUTAZIONE_DEFAULT = {
    "obbligazione": "scadenza", "strutturato": "scadenza", "etf_azioni": "mercato",
    "opzione": "mercato", "alternativo": "manuale", "liquidita": "mercato",
}

# Soglie del semaforo «distanza dalla barriera» (calo ancora possibile del sottostante peggiore)
SOGLIA_VERDE = 0.25
SOGLIA_GIALLO = 0.10

# Tolleranza del doppio controllo fra le due fonti di prezzo
TOLLERANZA_PREZZI = 0.015

DISCLAIMER = (
    "Il presente documento ha scopo puramente informativo e non costituisce offerta, raccomandazione "
    "o consulenza legale o fiscale. I dati provengono dagli estratti conto delle banche depositarie e da fonti di mercato "
    "pubbliche; i rendimenti passati non sono indicativi di quelli futuri. Per i prodotti portati a scadenza la valutazione "
    "al costo non riflette il prezzo di mercato attuale, che può essere inferiore o superiore."
)
