"""Tema scuro dell'app (i programmi di contabilità sono bianchi, quelli di finanza neri)."""

from __future__ import annotations

import base64

import streamlit as st

from core.config import ASSET

_CSS = """
<style>
:root { --bg:#000000; --pannello:#0D0D0F; --bordo:#26262A; --testo:#F2F2F2; --tenue:#9A9AA2; --accento:#FFFFFF; --verde:#34A853; --giallo:#FBBC04; --rosso:#EA4335; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] { background:var(--bg) !important; color:var(--testo); }
[data-testid="stHeader"] { background:transparent; }
.block-container { max-width: 1280px; padding-top: 2.2rem; }
h1,h2,h3,h4 { color:#FFFFFF; letter-spacing:-0.01em; }
h3 { font-weight:650; }
[data-testid="stCaptionContainer"], .stCaption { color:var(--tenue) !important; }

/* barra laterale */
[data-testid="stSidebar"] { background:#08080A !important; border-right:1px solid #1B1B1F; }
[data-testid="stSidebar"] h3 { font-size:1.05rem; margin-bottom:0; }
[data-testid="stSidebar"] .stButton > button { justify-content:flex-start; text-align:left; background:transparent; border:1px solid transparent; color:#D6D6DA; border-radius:999px; padding:0.45rem 0.9rem; }
[data-testid="stSidebar"] .stButton > button:hover { background:#17171B; color:#FFFFFF; border-color:#17171B; }
.st-key-side_attivo .stButton > button { background:#FFFFFF !important; color:#000000 !important; font-weight:650; border-color:#FFFFFF !important; }
.linea-menu { height:1px; width:48%; background:rgba(255,255,255,0.35); margin:10px 0 10px 0.7rem; }

/* pulsanti */
.stButton > button, .stDownloadButton > button { border-radius:10px; border:1px solid var(--bordo); background:#141418; color:var(--testo); }
.stButton > button:hover, .stDownloadButton > button:hover { border-color:#FFFFFF; color:#FFFFFF; background:#1B1B20; }
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:#FFFFFF; color:#000000; border-color:#FFFFFF; font-weight:650; }
.stButton > button[kind="primary"]:hover { background:#E6E6E6; color:#000000; }
.stButton > button:disabled { opacity:0.35; }

/* pulsanti con bordo colorato: salva = verde, elimina = rosso, modifica/attenzione = giallo */
[class*="st-key-btn_verde"] button { background:#0D0D0F !important; color:#34A853 !important; border:1.5px solid #34A853 !important; font-weight:600; }
[class*="st-key-btn_verde"] button:hover { background:#34A853 !important; color:#000000 !important; }
[class*="st-key-btn_rosso"] button { background:#0D0D0F !important; color:#EA4335 !important; border:1.5px solid #EA4335 !important; font-weight:600; }
[class*="st-key-btn_rosso"] button:hover { background:#EA4335 !important; color:#000000 !important; }
[class*="st-key-btn_blu"] button { background:#0D0D0F !important; color:#7C9CFF !important; border:1.5px solid #2B4FD9 !important; font-weight:600; }
[class*="st-key-btn_blu"] button:hover { background:#2B4FD9 !important; color:#FFFFFF !important; }
[class*="st-key-btn_giallo"] button { background:#0D0D0F !important; color:#FBBC04 !important; border:1.5px solid #FBBC04 !important; font-weight:600; }
[class*="st-key-btn_giallo"] button:hover { background:#FBBC04 !important; color:#000000 !important; }

/* riquadri, tabelle, campi */
[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--bordo) !important; border-radius:14px; background:var(--pannello); }
[data-testid="stMetric"] { background:var(--pannello); border:1px solid var(--bordo); border-radius:12px; padding:0.8rem 1rem; }
[data-testid="stMetricLabel"] { color:var(--tenue); }
[data-testid="stMetricValue"] { font-size:1.45rem; }
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, [data-baseweb="select"] > div { background:#101013 !important; border-color:var(--bordo) !important; color:var(--testo) !important; }
[data-testid="stTabs"] [role="tab"] { color:var(--tenue); }
[data-testid="stTabs"] [aria-selected="true"] { color:#FFFFFF; }
[data-testid="stExpander"] { border:1px solid var(--bordo); border-radius:12px; background:var(--pannello); }
hr { border-color:#1E1E22; }

/* home */
.hero-etichetta { font-size:0.72rem; letter-spacing:0.16em; color:var(--tenue); margin-bottom:0.2rem; }
.tile-icona { width:44px; height:44px; border-radius:12px; display:flex; align-items:center; justify-content:center; background:#17171B; margin-bottom:0.5rem; }
.sem { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }
.sem-verde { background:var(--verde); } .sem-giallo { background:var(--giallo); } .sem-rosso { background:var(--rosso); }

/* stato cloud (in basso a sinistra) */
.cloud-fisso { position:fixed; left:1rem; bottom:0.9rem; z-index:999; font-size:0.76rem; color:#FFFFFF; display:flex; align-items:center; gap:7px; }
.cloud-pallino { width:8px; height:8px; border-radius:50%; display:inline-block; }
.cloud-verde { background:#22C55E; box-shadow:0 0 5px #22C55E; } .cloud-giallo { background:#F59E0B; box-shadow:0 0 5px #F59E0B; }

/* accesso */
.accesso-titolo { text-align:center; font-size:0.95rem; letter-spacing:0.12em; color:var(--tenue); margin:1rem 0 0.4rem; }
.accesso-errore { text-align:center; color:#EA4335; font-size:0.85rem; }
</style>
"""

_CSS_ACCESSO = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none !important; }
.block-container { padding-top: 14vh; }
</style>
"""


def applica_stile() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def nascondi_barra_laterale() -> None:
    st.markdown(_CSS_ACCESSO, unsafe_allow_html=True)


def logo_html(larghezza_px: int = 200, centrato: bool = False) -> str:
    p = ASSET / "logo_ui.png"
    if not p.exists():
        return ""
    b64 = base64.b64encode(p.read_bytes()).decode()
    stile = f"width:{larghezza_px}px;" + ("display:block;margin:0 auto;" if centrato else "")
    return f"<img src='data:image/png;base64,{b64}' style='{stile}'/>"


def intestazione(titolo: str, sottotitolo: str = "") -> None:
    st.markdown(f"## {titolo}")
    if sottotitolo:
        st.caption(sottotitolo)


def semaforo(colore: str, testo: str) -> str:
    return f"<span class='sem sem-{colore}'></span>{testo}"


def bottone(etichetta: str, colore: str, chiave: str, **kw) -> bool:
    """Pulsante con bordo colorato: colore = 'verde' (salva/conferma), 'rosso' (elimina), 'giallo' (modifica/attenzione)."""
    with st.container(key=f"btn_{colore}_{chiave}"):
        return st.button(etichetta, key=chiave, **kw)
