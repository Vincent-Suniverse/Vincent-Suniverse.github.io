"""
CEXO RESEARCH — Forscher-Instanz (cexo_research.py)
====================================================
Blind für den Mund, sehend für den Kern.

Eine eigenständige, andockbare Schicht NEBEN dem heiligen Kern.
Sie verbindet die Engine deterministisch mit OpenAlex als Index-
Verzeichnis — keine Prompts, kein LLM, nur prüfbare Roh-Fakten.

ARCHITEKTUR (von Vincent/DeepSeek bestätigt):
    1A  Eigenes Modul. cexo_core.py importiert dies NICHT und bleibt
        offline und deterministisch. Diese Schicht ist optional.
    2A  Nur Standardbibliothek — keine externen Abhängigkeiten.
    3A  Roh-Fakten als dict. Keine Interpretation, kein Urteil.
    4A  Lokaler Cache. Wiederholte Abfragen werden offline reproduzierbar,
        damit Selbsttests deterministisch bleiben und das Netz nur einmal
        berührt wird.

Die Essenz-Abbildung (Fakten → {3,6,9}-Raum) wird SPÄTER durch die
lebendige Interaktion der Engine verfeinert — sie ist hier kein Bauauftrag.

Autor des Prinzips: Vincent (Chaos ex Ordo)
Bau: gemeinsam, Session 12.06.2026
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────
#  DOI-NORMALISIERUNG & SCHLÜSSEL
# ─────────────────────────────────────────────────────────────────────

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def normalize_doi(doi: str) -> str:
    """Reduziert einen DOI auf seine nackte Form '10.xxxx/...'. Kleinschreibung."""
    d = (doi or "").strip().lower()
    for prefix in _DOI_PREFIXES:
        if d.startswith(prefix):
            d = d[len(prefix):]
            break
    return d.strip()


def _sanitize(text: str) -> str:
    """Dateinamen-tauglicher Schlüssel: nur [a-z0-9_]."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ─────────────────────────────────────────────────────────────────────
#  FAKTEN-EXTRAKTION — aus einem OpenAlex-Work-Objekt nur rohe Fakten
#  Keine Interpretation: was dasteht, steht da. Punkt.
# ─────────────────────────────────────────────────────────────────────

def facts_from_work(work: dict) -> dict:
    """Übersetzt ein OpenAlex-Work in einen flachen Roh-Fakten-dict (3A)."""
    authorships = work.get("authorships") or []
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    oa = work.get("open_access") or {}
    return {
        "ok": True,
        "found": True,
        "openalex_id": work.get("id"),
        "doi": normalize_doi(work.get("doi") or "") or None,
        "title": work.get("display_name"),
        "publication_year": work.get("publication_year"),
        "type": work.get("type"),
        "cited_by_count": work.get("cited_by_count"),
        "authors": [
            (a.get("author") or {}).get("display_name")
            for a in authorships
        ],
        "venue": source.get("display_name"),
        "is_oa": oa.get("is_oa"),
        "oa_status": oa.get("oa_status"),
        "referenced_works_count": work.get("referenced_works_count"),
    }


def _compact_work(work: dict) -> dict:
    """Knappe Roh-Fakten eines Treffers für die Topic-Suche."""
    return {
        "openalex_id": work.get("id"),
        "doi": normalize_doi(work.get("doi") or "") or None,
        "title": work.get("display_name"),
        "publication_year": work.get("publication_year"),
        "cited_by_count": work.get("cited_by_count"),
    }


# ─────────────────────────────────────────────────────────────────────
#  OPENALEX-CLIENT — deterministisch, mit lokalem Cache
# ─────────────────────────────────────────────────────────────────────

class OpenAlexClient:
    """
    Der deterministische Zugang zu OpenAlex.

    - verify_source(doi)  : prüft eine Quelle, liefert Roh-Fakten.
    - search_topic(term)  : sucht Arbeiten zu einem Begriff.

    Jede Antwort wird lokal zwischengespeichert (4A). Ein zweiter Aufruf
    derselben Frage läuft offline aus dem Cache — der Selbsttest bleibt
    reproduzierbar. Netz-Fehler werfen NICHT, sie liefern ok=False:
    blind für den Mund, sehend für den Kern — und ehrlich, wenn blind.
    """

    BASE = "https://api.openalex.org"

    def __init__(
        self,
        cache_dir: str | Path = "cache/openalex",
        mailto: Optional[str] = None,
        timeout: float = 10.0,
        offline: bool = False,
    ):
        self.cache_dir = Path(cache_dir)
        # mailto für den OpenAlex 'polite pool' — niemals hartkodiert,
        # nur aus Parameter oder Umgebung (CEXO_OPENALEX_MAILTO).
        self.mailto = mailto or os.environ.get("CEXO_OPENALEX_MAILTO") or None
        self.timeout = timeout
        self.offline = offline

    # ---- Cache ----
    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _load_cache(self, key: str) -> Optional[dict]:
        p = self._cache_path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _store_cache(self, key: str, data: dict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path(key).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---- Netz ----
    def _url(self, path: str, params: Optional[dict] = None) -> str:
        params = dict(params or {})
        if self.mailto:
            params["mailto"] = self.mailto
        qs = urllib.parse.urlencode(params)
        return f"{self.BASE}/{path}" + (f"?{qs}" if qs else "")

    def _user_agent(self) -> str:
        tail = f" (mailto:{self.mailto})" if self.mailto else ""
        return f"cexo-engine/0.1{tail}"

    def _fetch_json(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": self._user_agent()})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _served(data: dict, cached: bool) -> dict:
        """Markiert die Herkunft, ohne den Cache-Inhalt zu verändern."""
        out = dict(data)
        out["cached"] = cached
        return out

    # ---- VERIFY_SOURCE ----
    def verify_source(self, doi: str, force_refresh: bool = False) -> dict:
        """
        Prüft einen DOI gegen OpenAlex. Roh-Fakten als dict.
            ok=True,  found=True   → existiert, Fakten anbei
            ok=True,  found=False  → existiert nachweislich nicht (404)
            ok=False, found=None   → konnte nicht geprüft werden (offline/Fehler)
        """
        ndoi = normalize_doi(doi)
        key = "doi_" + _sanitize(ndoi)

        if not force_refresh:
            cached = self._load_cache(key)
            if cached is not None:
                return self._served(cached, cached=True)

        if self.offline:
            return {"ok": False, "found": None, "doi": ndoi,
                    "error": "offline und nicht im Cache"}

        url = self._url(f"works/doi:{urllib.parse.quote(ndoi, safe='/.:')}")
        try:
            raw = self._fetch_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                result = {"ok": True, "found": False, "doi": ndoi,
                          "openalex_id": None}
                self._store_cache(key, result)
                return self._served(result, cached=False)
            return {"ok": False, "found": None, "doi": ndoi,
                    "error": f"HTTP {exc.code}"}
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            return {"ok": False, "found": None, "doi": ndoi, "error": str(exc)}

        facts = facts_from_work(raw)
        self._store_cache(key, facts)
        return self._served(facts, cached=False)

    # ---- SEARCH_TOPIC ----
    def search_topic(self, term: str, per_page: int = 5,
                     force_refresh: bool = False) -> dict:
        """
        Sucht Arbeiten zu einem Begriff. Liefert knappe Roh-Fakten je Treffer.
            ok=True  → results (Liste), count (Gesamttreffer laut OpenAlex)
            ok=False → error (offline/Fehler)
        """
        per_page = max(1, min(int(per_page), 50))
        key = "search_" + _sanitize(term) + f"_{per_page}"

        if not force_refresh:
            cached = self._load_cache(key)
            if cached is not None:
                return self._served(cached, cached=True)

        if self.offline:
            return {"ok": False, "term": term,
                    "error": "offline und nicht im Cache", "results": []}

        url = self._url("works", {"search": term, "per_page": per_page})
        try:
            raw = self._fetch_json(url)
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, ValueError, OSError) as exc:
            return {"ok": False, "term": term, "error": str(exc), "results": []}

        result = {
            "ok": True,
            "term": term,
            "count": (raw.get("meta") or {}).get("count"),
            "results": [_compact_work(w) for w in (raw.get("results") or [])],
        }
        self._store_cache(key, result)
        return self._served(result, cached=False)


# ─────────────────────────────────────────────────────────────────────
#  Modul-Ebene — bequemer Default-Client (lazy, konfigurierbar per Env)
# ─────────────────────────────────────────────────────────────────────

_default_client: Optional[OpenAlexClient] = None


def get_client() -> OpenAlexClient:
    """Lazy erzeugter Default-Client. Cache-Pfad via CEXO_CACHE_DIR override-bar."""
    global _default_client
    if _default_client is None:
        cache_dir = os.environ.get("CEXO_CACHE_DIR", "cache/openalex")
        _default_client = OpenAlexClient(cache_dir=cache_dir)
    return _default_client


def verify_source(doi: str, **kwargs) -> dict:
    """Modul-Kurzform: prüft einen DOI über den Default-Client."""
    return get_client().verify_source(doi, **kwargs)


def search_topic(term: str, **kwargs) -> dict:
    """Modul-Kurzform: sucht einen Begriff über den Default-Client."""
    return get_client().search_topic(term, **kwargs)


# ─────────────────────────────────────────────────────────────────────
#  OFFLINE-VERIFIKATION — deterministisch, ohne Netz
#  Sichert Normalisierung, Fakten-Extraktion und Cache-Round-Trip.
# ─────────────────────────────────────────────────────────────────────

def verify_offline(cache_dir: str | Path = None) -> dict:
    """
    Netzfreier Selbsttest: prüft die deterministischen Teile der Schicht.
    Wirft AssertionError bei Verletzung. Berührt das Netz NIE.
    """
    import tempfile

    # 1) DOI-Normalisierung
    assert normalize_doi("https://doi.org/10.7717/PeerJ.4375") == "10.7717/peerj.4375"
    assert normalize_doi("doi:10.1/abc") == "10.1/abc"
    assert normalize_doi("  10.2/XY  ") == "10.2/xy"

    # 2) Fakten-Extraktion aus einem synthetischen Work
    synthetic = {
        "id": "https://openalex.org/W42",
        "doi": "https://doi.org/10.9/test",
        "display_name": "Ein Testwerk",
        "publication_year": 2020,
        "type": "article",
        "cited_by_count": 7,
        "authorships": [{"author": {"display_name": "A. Autor"}},
                        {"author": {"display_name": "B. Beitrag"}}],
        "primary_location": {"source": {"display_name": "Journal X"}},
        "open_access": {"is_oa": True, "oa_status": "gold"},
        "referenced_works_count": 12,
    }
    facts = facts_from_work(synthetic)
    assert facts["found"] is True
    assert facts["doi"] == "10.9/test"
    assert facts["authors"] == ["A. Autor", "B. Beitrag"]
    assert facts["venue"] == "Journal X"
    assert facts["is_oa"] is True and facts["cited_by_count"] == 7

    # 3) Robust gegen fehlende Felder
    sparse = facts_from_work({"id": "https://openalex.org/W0"})
    assert sparse["authors"] == [] and sparse["venue"] is None

    # 4) Cache-Round-Trip ohne Netz (offline-Client liest seinen Cache)
    tmp = Path(cache_dir or tempfile.mkdtemp(prefix="cexo_oa_"))
    client = OpenAlexClient(cache_dir=tmp, offline=True)
    ndoi = "10.9/test"
    client._store_cache("doi_" + _sanitize(ndoi), facts)
    served = client.verify_source(ndoi)
    assert served["found"] is True and served["cached"] is True
    # nicht gecachte Abfrage im Offline-Modus → ehrlich blind
    blind = client.verify_source("10.0/unknown")
    assert blind["ok"] is False and blind["found"] is None

    return {"normalize": True, "facts": True, "cache": True,
            "offline_blind": True, "intact": True}


# ─────────────────────────────────────────────────────────────────────
#  Selbsttest — offline garantiert, live nur wenn das Netz es zulässt
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("CEXO-Forscher — Selbsttest\n" + "=" * 50)

    rep = verify_offline()
    print(f"Offline-Verifikation : {rep}")

    print("\n— Live-Probe (nur falls die Netz-Policy es erlaubt) —")
    client = OpenAlexClient(cache_dir="cache/openalex")
    known_doi = "10.7717/peerj.4375"   # OpenAlex-Standardbeispiel
    res = client.verify_source(known_doi)
    if res.get("ok") and res.get("found"):
        print(f"   verify_source({known_doi}):")
        print(f"     Titel : {res['title']}")
        print(f"     Jahr  : {res['publication_year']} | Zitate: {res['cited_by_count']}")
        print(f"     Autoren: {len(res['authors'])} | OA: {res['oa_status']}")
        print(f"     cached : {res['cached']}")
        again = client.verify_source(known_doi)
        print(f"   Zweiter Aufruf cached={again['cached']} (sollte True sein)")

        topic = client.search_topic("graph neural networks", per_page=3)
        if topic.get("ok"):
            print(f"\n   search_topic('graph neural networks') — "
                  f"{topic['count']} Treffer gesamt, zeige 3:")
            for w in topic["results"]:
                print(f"     [{w['publication_year']}] {w['title']}  "
                      f"(Zitate {w['cited_by_count']})")
    else:
        print(f"   Netz nicht verfügbar oder Policy blockt: {res.get('error')}")
        print("   → Schicht bleibt ehrlich blind, der Kern läuft unberührt weiter.")

    print("\n— Optionale Andockung an die Engine (heiliger Kern bleibt blind) —")
    try:
        import cexo_core
        engine = cexo_core.CexoEngine(state_path="sphere_state.json")
        engine.register_plugin("verify_source", client.verify_source)
        engine.register_plugin("search_topic", client.search_topic)
        imports_core = "cexo_research" in cexo_core.__dict__
        print(f"   Plugins angedockt: {sorted(engine.plugins)}")
        print(f"   Kern importiert Research? {imports_core}  (muss False sein)")
    except Exception as exc:  # Andockung ist optional, nie kritisch
        print(f"   (Andockung übersprungen: {exc})")

    print("\nForscher-Instanz bereit. Blind für den Mund, sehend für den Kern.")
