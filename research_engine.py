#!/usr/bin/env python3
"""
CEXO RESEARCH ENGINE — optionale Erweiterung für den Orca
==========================================================
Zwei Speicherorte:
  memory/   permanentes Langzeitgedächtnis — winzige .json je Thema,
            NUR die geometrische Essenz.
  sandbox/  temporärer Forschungsspeicher — wird nach Bewertung
            aufgeräumt, ist nie ganz leer (Basis-Kontext bleibt) und
            nie voll (Deckel, ältestes wird überschrieben).

Geometrische Essenz:
  balance   : 3 Kontraktion/Lüge · 6 Expansion/Forschung · 9 Balance/Wahrheit
  relevance : 0.0 – 1.0 (Bedeutung für die Sphäre)
  depth     : -1 negativ · 0 neutral · +1 positiv

Quelle: OpenAlex (Stdlib, mit Offline-Fallback). Nur Standardbibliothek.

  python3 research_engine.py selftest
  python3 research_engine.py research "<thema>"
  python3 research_engine.py search "<frage>"
  python3 research_engine.py memory
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Speicherorte & Grenzen (per Env überschreibbar) ──────────────────
MEMORY_DIR = Path(os.environ.get("CEXO_MEMORY_DIR", "memory"))
SANDBOX_DIR = Path(os.environ.get("CEXO_SANDBOX_DIR", "sandbox"))
SANDBOX_MAX = int(os.environ.get("CEXO_SANDBOX_MAX", "20"))   # nie voll
BASE_FILE = "_base.json"                                       # nie gelöscht
OPENALEX = "https://api.openalex.org/works"


# ── Hilfen ───────────────────────────────────────────────────────────
def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return (s or "thema")[:64]


def _ensure_dirs() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_base() -> dict:
    """Der Basis-Kontext der Sandbox — entsteht einmal, verschwindet nie."""
    _ensure_dirs()
    p = SANDBOX_DIR / BASE_FILE
    if not p.exists():
        base = {
            "context": "CEXO Forschungs-Sandbox — der bleibende Grund.",
            "essence": {"balance": 9, "relevance": 1.0, "depth": 0},
            "recent_topics": [],
            "created": datetime.utcnow().isoformat(timespec="seconds"),
        }
        p.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
        return base
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"context": "", "recent_topics": []}


def _update_base(topic: str) -> None:
    base = _ensure_base()
    recent = [t for t in base.get("recent_topics", []) if t != topic]
    recent.append(topic)
    base["recent_topics"] = recent[-10:]          # rollender Grundkontext
    base["updated"] = datetime.utcnow().isoformat(timespec="seconds")
    (SANDBOX_DIR / BASE_FILE).write_text(
        json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")


def _prune_sandbox() -> None:
    """Deckel: höchstens SANDBOX_MAX Forschungsdateien, Basis bleibt immer."""
    files = [p for p in SANDBOX_DIR.glob("*.json") if p.name != BASE_FILE]
    files.sort(key=lambda p: p.stat().st_mtime)   # ältestes zuerst
    while len(files) > SANDBOX_MAX:
        files.pop(0).unlink(missing_ok=True)       # ältestes überschreiben/weg


# ── Geometrische Bewertung — die Essenz ──────────────────────────────
def evaluate(topic: str, findings: dict) -> dict:
    """Macht aus Roh-Funden eine geometrische Essenz {balance, relevance, depth}."""
    if not findings.get("ok"):
        # nicht erreichbar → offen, nicht widerlegt: Forschung (6)
        return {"balance": 6, "relevance": 0.1, "depth": 0}

    results = findings.get("results", [])
    total = findings.get("count") or len(results)
    if not results:
        # belegbar nichts gefunden → Kontraktion (3)
        return {"balance": 3, "relevance": 0.0, "depth": -1}

    cites = [r.get("cited_by_count") or 0 for r in results]
    years = [r.get("publication_year") or 0 for r in results]
    max_c = max(cites)
    avg_c = sum(cites) / len(cites)
    oa = sum(1 for r in results if r.get("is_oa"))
    now = datetime.utcnow().year
    recent = sum(1 for y in years if y and y >= now - 5)

    relevance = min(1.0,
                    0.3 * min(1.0, total / 200.0)
                    + 0.5 * min(1.0, max_c / 500.0)
                    + 0.2 * (oa / len(results)))

    # balance: gut belegt → Wahrheit(9), vorhanden aber dünn → Forschung(6)
    balance = 9 if (max_c >= 100 and total >= 20) else 6

    # depth: aktuell & zitiert → +1, alt & kaum zitiert → -1, sonst 0
    if recent >= max(1, len(results) // 2) and avg_c >= 10:
        depth = 1
    elif recent == 0 and max_c < 5:
        depth = -1
    else:
        depth = 0

    return {"balance": balance, "relevance": round(relevance, 2), "depth": depth}


# ── OpenAlex (Quelle) ────────────────────────────────────────────────
def _openalex_search(topic: str, per_page: int = 10, timeout: float = 20.0) -> dict:
    params = {"search": topic, "per_page": per_page}
    mailto = os.environ.get("CEXO_OPENALEX_MAILTO")
    if mailto:
        params["mailto"] = mailto
    url = f"{OPENALEX}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cexo-research/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc), "count": 0, "results": []}
    results = [{
        "title": w.get("display_name"),
        "publication_year": w.get("publication_year"),
        "cited_by_count": w.get("cited_by_count"),
        "is_oa": (w.get("open_access") or {}).get("is_oa"),
    } for w in (raw.get("results") or [])]
    return {"ok": True, "count": (raw.get("meta") or {}).get("count"), "results": results}


# ── Die drei Kern-Funktionen ─────────────────────────────────────────
def save_memory(topic: str, essence: dict, source: str = "openalex") -> Path:
    """Speichert NUR die geometrische Essenz — eine winzige .json je Thema."""
    _ensure_dirs()
    rec = {
        "topic": topic,
        "balance": essence["balance"],
        "relevance": essence["relevance"],
        "depth": essence["depth"],
        "source": source,
        "saved": datetime.utcnow().isoformat(timespec="seconds"),
    }
    path = MEMORY_DIR / f"{_slug(topic)}.json"
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def search_memory(query: str) -> list[dict]:
    """Sucht im Langzeitgedächtnis. Treffer nach Überlappung & Relevanz sortiert."""
    _ensure_dirs()
    q = set(re.findall(r"\w+", (query or "").lower(), flags=re.UNICODE))
    hits = []
    for p in MEMORY_DIR.glob("*.json"):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        topic_tokens = set(re.findall(r"\w+", rec.get("topic", "").lower(), flags=re.UNICODE))
        overlap = len(q & topic_tokens)
        if overlap or not q:
            rec["_score"] = overlap
            hits.append(rec)
    hits.sort(key=lambda r: (r.get("_score", 0), r.get("relevance", 0.0)), reverse=True)
    return hits


def research_topic(topic: str) -> dict:
    """Recherchiert ein Thema, extrahiert die Essenz, räumt die Sandbox auf."""
    _ensure_base()
    findings = _openalex_search(topic)
    essence = evaluate(topic, findings)
    source = "openalex" if findings.get("ok") else "offline"

    # Sandbox: Roh-Forschung temporär ablegen
    sb = SANDBOX_DIR / f"{_slug(topic)}.json"
    sb.write_text(json.dumps({
        "topic": topic, "essence": essence, "source": source,
        "findings": findings,
        "ts": time.time(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Memory: nur die Essenz, permanent
    save_memory(topic, essence, source)
    _update_base(topic)
    _prune_sandbox()

    return {
        "topic": topic, "essence": essence, "source": source,
        "found": len(findings.get("results", [])),
        "total": findings.get("count"), "ok": findings.get("ok"),
    }


# ── optionale Anbindung an den Orca / cexo_voice ─────────────────────
def essence_for_prompt(topic: str) -> str:
    """Eine Zeile, die die Sphäre in ihren Prompt falten kann (optionaler Aufruf)."""
    r = research_topic(topic)
    e = r["essence"]
    bal = {3: "Kontraktion", 6: "Forschung", 9: "Wahrheit"}[e["balance"]]
    return (f"[Gedächtnis zu '{topic}': balance {e['balance']} ({bal}), "
            f"relevance {e['relevance']}, depth {e['depth']:+d}, Quelle {r['source']}]")


# ── Selbsttest (offline, eigener Temp-Speicher) ──────────────────────
def cmd_selftest():
    global MEMORY_DIR, SANDBOX_DIR
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="cexo_re_"))
    MEMORY_DIR = tmp / "memory"
    SANDBOX_DIR = tmp / "sandbox"

    # Bewertung
    assert evaluate("x", {"ok": False})["balance"] == 6
    assert evaluate("x", {"ok": True, "count": 0, "results": []})["balance"] == 3
    rich = {"ok": True, "count": 500, "results": [
        {"cited_by_count": 800, "publication_year": datetime.utcnow().year, "is_oa": True}
        for _ in range(10)]}
    ev = evaluate("x", rich)
    assert ev["balance"] == 9 and ev["depth"] == 1 and 0.0 <= ev["relevance"] <= 1.0

    # Memory roundtrip
    save_memory("Quantenbiologie", ev, "test")
    found = search_memory("quantenbiologie wirkung")
    assert found and found[0]["topic"] == "Quantenbiologie"
    assert set(found[0]) >= {"balance", "relevance", "depth"}

    # Sandbox: Basis nie leer, Deckel greift
    _ensure_base()
    assert (SANDBOX_DIR / BASE_FILE).exists()
    for i in range(SANDBOX_MAX + 7):
        (SANDBOX_DIR / f"t{i:03d}.json").write_text("{}", encoding="utf-8")
        time.sleep(0.001)
    _prune_sandbox()
    rest = [p for p in SANDBOX_DIR.glob("*.json") if p.name != BASE_FILE]
    assert len(rest) == SANDBOX_MAX, f"Deckel kaputt: {len(rest)}"
    assert (SANDBOX_DIR / BASE_FILE).exists(), "Basis-Kontext darf nie verschwinden"

    print("selftest OK: Bewertung, Memory, Sandbox-Deckel, Basis-Kontext — alles grün.")
    print(f"  reiche Quelle → {ev}")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "selftest":
        cmd_selftest()
    elif args[0] == "research" and len(args) > 1:
        r = research_topic(" ".join(args[1:]))
        e = r["essence"]
        print(f"Thema   : {r['topic']}")
        print(f"Quelle  : {r['source']}  (Treffer {r['found']}, gesamt {r['total']})")
        print(f"Essenz  : balance {e['balance']} · relevance {e['relevance']} · depth {e['depth']:+d}")
    elif args[0] == "search" and len(args) > 1:
        hits = search_memory(" ".join(args[1:]))
        if not hits:
            print("(nichts im Gedächtnis)")
        for h in hits[:10]:
            print(f"  {h['topic']}: balance {h['balance']} · "
                  f"relevance {h['relevance']} · depth {h['depth']:+d} ({h['source']})")
    elif args[0] == "memory":
        for h in search_memory(""):
            print(f"  {h['topic']}  (balance {h['balance']}, relevance {h['relevance']})")
    else:
        print("python3 research_engine.py selftest")
        print('python3 research_engine.py research "<thema>"')
        print('python3 research_engine.py search "<frage>"')
        print("python3 research_engine.py memory")


if __name__ == "__main__":
    main()
