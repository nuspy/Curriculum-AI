"""Funzioni di normalizzazione e hashing per identità annunci e deduplica (piano §6)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Parametri di tracking da rimuovere dall'URL di candidatura (oltre a tutti gli utm_*)
_TRACKING_PARAMS = {
    "gclid", "fbclid", "msclkid", "dclid", "yclid", "igshid",
    "ref", "referrer", "source", "src", "trk", "trkparams",
    "mc_cid", "mc_eid", "campaign",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_text(s: str | None) -> str:
    """lowercase, senza accenti, solo alfanumerici separati da spazio singolo."""
    if not s:
        return ""
    s = _strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def normalize_apply_url(url: str | None) -> str:
    """URL candidatura canonico: scheme/host lowercase, no www, no fragment,
    senza parametri di tracking, query ordinata."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/") or "/"
    q = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not (k.lower().startswith("utm_") or k.lower() in _TRACKING_PARAMS)
    ]
    q.sort()
    return urlunsplit((scheme, netloc, path, urlencode(q), ""))


def content_hash(
    *,
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> str:
    """Hash del contenuto annuncio (dedup ripubblicazioni stesso portale)."""
    basis = "|".join(normalize_text(x) for x in (title, company, location, description))
    return _sha(basis)


def job_fingerprint(
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
) -> str:
    """Fingerprint fuzzy (stesso ruolo su portali diversi)."""
    return _sha("|".join(normalize_text(x) for x in (company, title, location)))


def canonical_job_key(
    *,
    apply_url: str | None = None,
    portal_slug: str | None = None,
    external_id: str | None = None,
) -> str:
    """Chiave canonica forte: preferisce portal_slug+external_id, altrimenti l'URL normalizzato."""
    if portal_slug and external_id:
        return _sha(f"{normalize_text(portal_slug)}:{str(external_id).strip().lower()}")
    return _sha(normalize_apply_url(apply_url))


def normalize_question(q: str | None) -> str:
    """Normalizza il testo di una domanda per il lookup in approved_answers."""
    if not q:
        return ""
    s = _strip_accents(q).lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s.rstrip("?:.! ").strip()
