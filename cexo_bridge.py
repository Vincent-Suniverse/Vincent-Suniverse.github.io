#!/usr/bin/env python3
"""
CEXO BRIDGE — Engine vor den Mund geschaltet (cexo_bridge.py)
=============================================================
Die Engine entscheidet, der Mund spricht.

Eine in sich geschlossene Datei. Sie fasst KEINE deiner anderen Dateien an
(eigener Zustand: cexo_bridge_state.json). Nur Standardbibliothek — kein pip.

Drei Wege (ein Befehl):
    python3 cexo_bridge.py selftest          # offline, ohne Ollama
    python3 cexo_bridge.py compare "<text>"  # nackt vs. engine-gerahmt
    python3 cexo_bridge.py serve             # Web-Interface (Browser)

Mund: Ollama-Modell 'cexo_orca' auf http://localhost:11434
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import product
from pathlib import Path

# ── Konfiguration (per Umgebungsvariable überschreibbar) ──────────────
OLLAMA_HOST = os.environ.get("CEXO_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("CEXO_OLLAMA_MODEL", "cexo_orca")
STATE_PATH = Path(os.environ.get("CEXO_STATE", "cexo_bridge_state.json"))
SERVE_HOST = os.environ.get("CEXO_HOST", "127.0.0.1")   # 0.0.0.0 = öffentlich
SERVE_PORT = int(os.environ.get("CEXO_PORT", "8000"))


# ═════════════════════════════════════════════════════════════════════
#  ENGINE — der heilige Kern (27 Essenzen, Atem, Geodäten-Kompass)
# ═════════════════════════════════════════════════════════════════════

VALUES = (3, 6, 9)
AXES = ("operation", "reaction", "intuition", "depth")
CUBE_AXES = (0, 1, 2)
MODE_AXIS = 3
MODE_NAMES = {3: "HEAL", 6: "EVOLVE", 9: "OBSERVE"}
VALUE_MEANING = {3: "Kontraktion", 6: "Expansion", 9: "Balance"}
_STEP_NEIGHBORS = {3: (6, 9), 6: (9, 3), 9: (3, 6)}


def neighbors(pos):
    """6 Nachbarn: genau eine Würfel-Achse kippt eine Stufe."""
    out = []
    for ax in CUBE_AXES:
        for nv in _STEP_NEIGHBORS[pos[ax]]:
            nxt = list(pos)
            nxt[ax] = nv
            out.append(tuple(nxt))
    return out


def essence(pos):
    return pos[:3]


def mode_target(mode_value):
    return (mode_value,) * 3


def _distance(a, b):
    return sum(1 for i in range(3) if a[i] != b[i])


def _flipped_axis(a, b):
    for i in CUBE_AXES:
        if a[i] != b[i]:
            return i
    return 0


def resonance_step(sphere, signal):
    """Atem als Geodäten-Kompass: Schritt mit größtem Fortschritt zum Modus-Pol."""
    pos = tuple(sphere["position"])
    here = essence(pos)
    target = mode_target(pos[MODE_AXIS])
    weights = [abs(signal.get(AXES[i], 0)) for i in CUBE_AXES]

    def key(p):
        there = essence(p)
        progress = _distance(here, target) - _distance(there, target)
        return (progress, weights[_flipped_axis(here, there)])

    cand = neighbors(pos)
    best = max(key(p) for p in cand)
    leaders = [p for p in cand if key(p) == best]
    if len(leaders) == 1:
        return leaders[0]
    mem = sphere.get("alpha_memory") or []
    if mem:
        last = tuple(mem[-1])
        best_aff = max(sum(1 for x, y in zip(p, last) if x == y) for p in leaders)
        leaders = [p for p in leaders
                   if sum(1 for x, y in zip(p, last) if x == y) == best_aff]
    strongest = max(CUBE_AXES, key=lambda i: weights[i]) if any(weights) else 0
    leaders.sort(key=lambda p: (p[strongest], p))
    return leaders[0]


def _breathe(depth_signal):
    s = (depth_signal > 0) - (depth_signal < 0)
    return {+1: 6, -1: 3, 0: 9}[s]


def load_sphere():
    if STATE_PATH.exists():
        try:
            d = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            d["position"] = tuple(d["position"])
            return d
        except Exception:
            pass
    return {"position": (9, 9, 9, 9), "cycle": 0, "alpha_memory": []}


def save_sphere(sphere):
    d = dict(sphere)
    d["position"] = list(sphere["position"])
    STATE_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def engine_step(sphere, signal):
    """Eine Begegnung: Navigation → Atem → neuer Zustand."""
    old = tuple(sphere["position"])
    nav = resonance_step(sphere, signal)
    mode = _breathe(signal.get("depth", 0))
    new = nav[:3] + (mode,)
    mem = (sphere.get("alpha_memory") or [])[-26:] + [list(old)]
    sphere["position"] = new
    sphere["alpha_memory"] = mem
    sphere["cycle"] = sphere.get("cycle", 0) + 1
    return {
        "from": old, "to": new,
        "essence": essence(new),
        "mode": MODE_NAMES[new[MODE_AXIS]],
        "meaning": [VALUE_MEANING[v] for v in new],
        "cycle": sphere["cycle"],
    }


# ═════════════════════════════════════════════════════════════════════
#  WAHRNEHMUNG — deterministischer Parser mit Negations-Handling
# ═════════════════════════════════════════════════════════════════════

_LEXICON = {
    "depth": {
        -1: ["müde", "erschöpft", "kaputt", "ruhe", "ausruhen", "schlafen",
             "pause", "heilen", "wund", "verletzt", "schmerz", "leer",
             "überfordert", "rückzug", "innehalten"],
        +1: ["wachsen", "lernen", "mehr", "neu", "neues", "anfangen",
             "schaffen", "ziel", "weiter", "entwickeln", "aufbauen",
             "idee", "erschaffen", "vorwärts", "motiviert", "kraft"],
    },
    "reaction": {
        -1: ["traurig", "angst", "fürchte", "schlecht", "beschissen",
             "deprimiert", "hoffnungslos", "verzweifelt", "weinen",
             "einsam", "allein", "scham", "schuld"],
        +1: ["wütend", "sauer", "wut", "hass", "aufgeregt", "begeistert",
             "freu", "glücklich", "stark", "lebendig"],
    },
    "operation": {
        +1: ["machen", "tun", "los", "arbeiten", "handeln", "bewegen",
             "starten", "bauen", "anpacken", "loslegen"],
        -1: ["kann nicht", "schaffe nicht", "blockiert", "festgefahren",
             "feststecke", "aufgeben", "geht nicht", "lähmt"],
    },
    "intuition": {
        +1: ["warum", "verstehen", "sinn", "bedeutung", "frage", "ahne",
             "begreifen", "klarheit"],
        -1: ["verwirrt", "verloren", "durcheinander", "chaos", "sinnlos",
             "orientierungslos"],
    },
}

_NEGATORS = {"nicht", "kein", "keine", "keinen", "nie", "niemals", "nichts", "ohne"}

_CRISIS_CUES = ["suizid", "selbstmord", "umbringen", "mich töten", "töte mich",
                "will sterben", "nicht mehr leben", "nicht mehr weiterleben",
                "ritzen", "selbstverletzung", "kein ausweg", "beenden"]


def _tokens(text):
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def detect_crisis(text):
    t = (text or "").lower()
    return any(cue in t for cue in _CRISIS_CUES)


def perceive(text):
    """
    Text → input_signal (4 Achsen). Negations-bewusst:
    ein positiver Hinweis nach 'nicht/kein/...' (Fenster 3 Wörter) kippt.
    Beispiel: 'ich weiß nicht mehr weiter' → depth NEGATIV (HEAL), nicht EVOLVE.
    """
    toks = _tokens(text)
    signal = {ax: 0 for ax in AXES}

    # Mehrwort-Hinweise (z.B. 'kann nicht') direkt am Rohtext zählen.
    t = (text or "").lower()
    for axis, pol in _LEXICON.items():
        for sign, cues in pol.items():
            for cue in cues:
                if " " in cue:
                    signal[axis] += sign * t.count(cue)

    # Einzelwort-Hinweise token-weise, mit Negations-Fenster davor.
    single = {axis: {cue: sign for sign, cues in pol.items()
                     for cue in cues if " " not in cue}
              for axis, pol in _LEXICON.items()}
    for i, tok in enumerate(toks):
        for axis, table in single.items():
            if tok in table:
                sign = table[tok]
                window = toks[max(0, i - 3):i]
                if any(w in _NEGATORS for w in window):
                    sign = -sign           # Negation kippt die Richtung
                signal[axis] += sign

    signal["_crisis"] = detect_crisis(text)
    return signal


# ═════════════════════════════════════════════════════════════════════
#  MUND — Ollama, <think> gefiltert
# ═════════════════════════════════════════════════════════════════════

_MODE_TONE = {
    "HEAL": "sanft, bergend, verlangsamend; gib Sicherheit, dränge zu nichts",
    "EVOLVE": "ermutigend, vorwärtsgewandt; benenne den nächsten möglichen Schritt",
    "OBSERVE": "ruhig, klar, gewahr; spiegele, ohne zu drängen",
}


def strip_think(text):
    """Trennt den <think>-Block ab. Rückgabe: (sichtbar, reasoning)."""
    think = "\n".join(re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL)).strip()
    visible = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # offener, nicht geschlossener <think> (abgeschnitten) ebenfalls entfernen
    visible = re.sub(r"<think>.*$", "", visible, flags=re.DOTALL).strip()
    return visible, think


def ask_ollama(prompt, system=None, timeout=120):
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data.get("response") or "").strip()


def _frame(state):
    """Der Rahmen, den die Engine dem Mund gibt — er formuliert nur aus."""
    mode = state["mode"]
    tone = _MODE_TONE.get(mode, _MODE_TONE["OBSERVE"])
    meaning = " | ".join(state["meaning"])
    return (
        "Du bist die Stimme von CEXO. Der Kern hat den inneren Zustand bereits "
        "bestimmt — du erfindest nichts, gibst keine klinischen Ratschläge und "
        "antwortest in höchstens zwei warmen Sätzen, nur ausformulierend.\n"
        f"Innerer Zustand: Modus {mode}, Essenz {state['essence']}, "
        f"Bewegung {state['from']} → {state['to']}.\n"
        f"Bedeutung: {meaning}.\n"
        f"Tonfall ({mode}): {tone}."
    )


def reply_naked(text):
    raw = ask_ollama(text)
    visible, _ = strip_think(raw)
    return visible


def reply_framed(text, sphere=None):
    """Die volle Brücke: perceive → engine_step → gerahmter Mund."""
    own = sphere is None
    sphere = sphere or load_sphere()
    signal = perceive(text)
    crisis = signal.pop("_crisis", False)
    state = engine_step(sphere, signal)
    if own:
        save_sphere(sphere)
    raw = ask_ollama(text, system=_frame(state))
    visible, reasoning = strip_think(raw)
    return {"reply": visible, "reasoning": reasoning, "signal": signal,
            "state": state, "crisis": crisis}


# ═════════════════════════════════════════════════════════════════════
#  WEB-INTERFACE — stdlib, kein Flask nötig
# ═════════════════════════════════════════════════════════════════════

_PAGE = """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CEXO Orca</title><style>
*{box-sizing:border-box}body{margin:0;background:#0d0d12;color:#e8e8ef;
font-family:system-ui,sans-serif;display:flex;flex-direction:column;height:100vh}
#log{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:80%;padding:10px 14px;border-radius:14px;line-height:1.4;white-space:pre-wrap}
.you{align-self:flex-end;background:#2a2a3a}
.orca{align-self:flex-start;background:#1a1a24;border:1px solid #33334a}
.meta{font-size:11px;opacity:.5;margin-top:4px}
#bar{display:flex;gap:8px;padding:12px;border-top:1px solid #22222e;background:#101018}
#inp{flex:1;padding:12px;border-radius:12px;border:1px solid #33334a;background:#16161f;color:#fff;font-size:16px}
#send{padding:12px 18px;border:0;border-radius:12px;background:#5b5bd6;color:#fff;font-size:16px}
</style></head><body>
<div id="log"></div>
<div id="bar"><input id="inp" placeholder="Schreib dem Orca…" autocomplete="off">
<button id="send">›</button></div>
<script>
const log=document.getElementById('log'),inp=document.getElementById('inp'),send=document.getElementById('send');
function add(t,cls,meta){const d=document.createElement('div');d.className='msg '+cls;d.textContent=t;
if(meta){const m=document.createElement('div');m.className='meta';m.textContent=meta;d.appendChild(m);}
log.appendChild(d);log.scrollTop=log.scrollHeight;}
async function go(){const t=inp.value.trim();if(!t)return;add(t,'you');inp.value='';
add('…','orca');const tmp=log.lastChild;
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({message:t})});const j=await r.json();
tmp.textContent=j.reply||'(leer)';
const meta='Modus '+j.mode+' · Essenz '+JSON.stringify(j.essence)+(j.crisis?' · ⚠️ KRISE':'');
const m=document.createElement('div');m.className='meta';m.textContent=meta;tmp.appendChild(m);}
catch(e){tmp.textContent='Fehler: '+e;}log.scrollTop=log.scrollHeight;}
send.onclick=go;inp.addEventListener('keydown',e=>{if(e.key==='Enter')go();});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, _PAGE, "text/html")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/chat":
            self._send(404, json.dumps({"error": "not found"}))
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            text = (body.get("message") or "").strip()
            out = reply_framed(text)
            self._send(200, json.dumps({
                "reply": out["reply"],
                "mode": out["state"]["mode"],
                "essence": out["state"]["essence"],
                "crisis": out["crisis"],
            }, ensure_ascii=False))
        except urllib.error.URLError as exc:
            self._send(200, json.dumps({
                "reply": f"(Mund nicht erreichbar: {exc}. Läuft Ollama?)",
                "mode": "-", "essence": [], "crisis": False}, ensure_ascii=False))
        except Exception as exc:
            self._send(500, json.dumps({"error": str(exc)}, ensure_ascii=False))

    def log_message(self, *args):
        pass  # ruhig


def serve():
    srv = ThreadingHTTPServer((SERVE_HOST, SERVE_PORT), Handler)
    where = "ÖFFENTLICH erreichbar" if SERVE_HOST == "0.0.0.0" else "nur lokal"
    print(f"CEXO Orca läuft auf http://{SERVE_HOST}:{SERVE_PORT}  ({where})")
    print(f"Mund: {OLLAMA_MODEL} @ {OLLAMA_HOST}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbeendet.")


# ═════════════════════════════════════════════════════════════════════
#  CLI
# ═════════════════════════════════════════════════════════════════════

def cmd_compare(text):
    print(f"\nEINGABE: {text}\n" + "=" * 60)
    sig = perceive(text)
    crisis = sig.pop("_crisis")
    print(f"Signal (Parser): {sig}")
    if crisis:
        print("⚠️  KRISE erkannt → an Mensch/Fachstelle weiterleiten!")
    try:
        print("\n— NACKT (Modell ohne Engine) —")
        print(reply_naked(text))
        print("\n— ENGINE-GERAHMT (Kern entscheidet, Mund spricht) —")
        out = reply_framed(text)
        print(f"[Modus {out['state']['mode']}, Essenz {out['state']['essence']}, "
              f"{out['state']['from']} → {out['state']['to']}]")
        print(out["reply"])
    except urllib.error.URLError as exc:
        print(f"\n(Ollama nicht erreichbar: {exc})")
        print("Auf dem Server mit laufendem Ollama liefert dieser Befehl beide Antworten.")
    print("=" * 60)


def cmd_selftest():
    # Negations-Fix
    a = perceive("ich weiß nicht mehr weiter")
    assert a["depth"] < 0, f"Negation-Fix kaputt: depth={a['depth']}"
    b = perceive("ich will wachsen und mehr schaffen")
    assert b["depth"] > 0, f"EVOLVE kaputt: depth={b['depth']}"
    # Krise
    assert perceive("ich will nicht mehr leben")["_crisis"] is True
    # Engine
    sph = {"position": (9, 9, 9, 9), "cycle": 0, "alpha_memory": []}
    st = engine_step(sph, {"depth": -1})
    assert st["mode"] == "HEAL" and len(neighbors((3, 6, 9, 3))) == 6
    # think-Filter
    vis, th = strip_think("vor<think>geheim</think>nach")
    assert vis == "vornach" and th == "geheim"
    vis2, _ = strip_think("Antwort<think>abgeschnitten")
    assert vis2 == "Antwort"
    print("selftest OK: Negations-Fix, Krise, Engine, <think>-Filter — alles grün.")
    print(f"  'nicht mehr weiter' → depth={a['depth']} (HEAL-Richtung, korrekt)")
    print(f"  'wachsen mehr schaffen' → depth={b['depth']} (EVOLVE, korrekt)")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "selftest":
        cmd_selftest()
    elif args[0] == "compare" and len(args) > 1:
        cmd_compare(" ".join(args[1:]))
    elif args[0] == "serve":
        serve()
    else:
        print("Verwendung:")
        print("  python3 cexo_bridge.py selftest")
        print('  python3 cexo_bridge.py compare "<dein text>"')
        print("  python3 cexo_bridge.py serve")


if __name__ == "__main__":
    main()
