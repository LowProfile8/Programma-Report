"""Archivio dei dati: Supabase se collegato, altrimenti file locali (solo per prove: si azzerano su Streamlit Cloud).

Due tabelle in Supabase (vedi supabase_schema.sql):
  documenti(collezione, id, dati jsonb, aggiornato)   -> clienti, strumenti, report, prezzi manuali
  file(id, b64)                                       -> i PDF dei report
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import DATI_LOCALI


def _secret(nome: str) -> Optional[str]:
    try:
        import streamlit as st
        v = st.secrets.get(nome)
        return str(v) if v else None
    except Exception:
        return None


def nuovo_id() -> str:
    return uuid.uuid4().hex[:12]


def _sicuro(nome: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", nome)


class ArchivioLocale:
    nome = "locale"

    def __init__(self, radice: Path = DATI_LOCALI):
        self.radice = radice

    def _p(self, coll, id_):
        return self.radice / _sicuro(coll) / f"{_sicuro(id_)}.json"

    def leggi(self, coll, id_):
        p = self._p(coll, id_)
        return json.loads(p.read_text()) if p.exists() else None

    def scrivi(self, coll, id_, dati):
        p = self._p(coll, id_)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dati, ensure_ascii=False))

    def elenca(self, coll):
        cartella = self.radice / _sicuro(coll)
        if not cartella.exists():
            return []
        return [json.loads(p.read_text()) for p in sorted(cartella.glob("*.json"))]

    def elimina(self, coll, id_):
        p = self._p(coll, id_)
        if p.exists():
            p.unlink()

    def salva_file(self, id_, dati: bytes):
        p = self.radice / "file" / _sicuro(id_)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dati)

    def leggi_file(self, id_) -> Optional[bytes]:
        p = self.radice / "file" / _sicuro(id_)
        return p.read_bytes() if p.exists() else None

    def elimina_file(self, id_):
        p = self.radice / "file" / _sicuro(id_)
        if p.exists():
            p.unlink()

    def verifica(self):
        return "locale", "dati salvati solo su questo computer"


class ArchivioSupabase:
    nome = "supabase"

    def __init__(self, url: str, chiave: str):
        from supabase import create_client
        self.c = create_client(url, chiave)

    def leggi(self, coll, id_):
        r = self.c.table("documenti").select("dati").eq("collezione", coll).eq("id", id_).limit(1).execute()
        return r.data[0]["dati"] if r.data else None

    def scrivi(self, coll, id_, dati):
        self.c.table("documenti").upsert({"collezione": coll, "id": id_, "dati": dati, "aggiornato": datetime.utcnow().isoformat()}).execute()

    def elenca(self, coll):
        r = self.c.table("documenti").select("dati").eq("collezione", coll).execute()
        return [x["dati"] for x in r.data]

    def elimina(self, coll, id_):
        self.c.table("documenti").delete().eq("collezione", coll).eq("id", id_).execute()

    def salva_file(self, id_, dati: bytes):
        self.c.table("file").upsert({"id": id_, "b64": base64.b64encode(dati).decode()}).execute()

    def leggi_file(self, id_):
        r = self.c.table("file").select("b64").eq("id", id_).limit(1).execute()
        return base64.b64decode(r.data[0]["b64"]) if r.data else None

    def elimina_file(self, id_):
        self.c.table("file").delete().eq("id", id_).execute()

    def verifica(self):
        self.c.table("documenti").select("id").limit(1).execute()
        return "attivo", "Supabase risponde"


_archivio = None
_errore_cloud = ""


def archivio():
    """Archivio in uso: Supabase se i secrets ci sono e rispondono, altrimenti locale."""
    global _archivio, _errore_cloud
    if _archivio is not None:
        return _archivio
    url, chiave = _secret("SUPABASE_URL"), _secret("SUPABASE_KEY")
    if url and chiave:
        try:
            a = ArchivioSupabase(url, chiave)
            a.verifica()
            _archivio = a
            return a
        except Exception as e:      # configurato ma non raggiungibile: NON si ripiega in silenzio sul locale
            _errore_cloud = str(e)[:200]
            raise ConnectionError(_errore_cloud)
    _archivio = ArchivioLocale()
    return _archivio


def stato_cloud() -> tuple[str, str]:
    """('attivo'|'locale'|'errore', dettaglio) — per il pallino in basso a sinistra."""
    url, chiave = _secret("SUPABASE_URL"), _secret("SUPABASE_KEY")
    if not (url and chiave):
        return "locale", "Supabase non configurato"
    try:
        return archivio().verifica()
    except Exception as e:
        return "errore", str(e)[:200]


def reimposta():
    global _archivio
    _archivio = None
