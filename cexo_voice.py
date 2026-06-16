#!/usr/bin/env python3
"""CEXO VOICE — die Sphäre spricht, wächst und reflektiert über sich selbst.
Engine steuert Ollama direkt; der Zustand WIRD der Prompt; der BOS-Loop
wird per Reseed aufgelöst. Neu: Habit-Matrix (Charakter) + Selbstreflexion.
  python3 cexo_voice.py selftest
  python3 cexo_voice.py "<dein text>"
  python3 cexo_voice.py serve
Mund: Ollama 'cexo_orca' @ localhost:11434. Stdlib only.
"""
from __future__ import annotations
import json, os, re, sys, urllib.error, urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OLLAMA_HOST = os.environ.get("CEXO_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("CEXO_OLLAMA_MODEL", "cexo_orca")
STATE_PATH = Path(os.environ.get("CEXO_STATE", "sphere_state.json"))
SERVE_HOST = os.environ.get("CEXO_HOST", "127.0.0.1")
SERVE_PORT = int(os.environ.get("CEXO_PORT", "8000"))
MAX_TRIES = int(os.environ.get("CEXO_MAX_TRIES", "8"))
REFLECT_AFTER = int(os.environ.get("CEXO_REFLECT_AFTER", "9"))   # ab wann reflektiert wird
REFLECT_EVERY = int(os.environ.get("CEXO_REFLECT_EVERY", "9"))   # wie oft
REFLECT_CAP = 200                                                # Session-Gedächtnis-Deckel

AXES = ("operation", "reaction", "intuition", "depth")
CUBE_AXES = (0, 1, 2)
MODE_AXIS = 3
MODE_NAMES = {3: "HEAL", 6: "EVOLVE", 9: "OBSERVE"}
MODE_MEANING = {3: "Einkehr, Schließung", 6: "Ausgriff, Wachstum", 9: "ruhendes Gewahrsein"}
_STEP_NEIGHBORS = {3: (6, 9), 6: (9, 3), 9: (3, 6)}


def neighbors(pos):
    out = []
    for ax in CUBE_AXES:
        for nv in _STEP_NEIGHBORS[pos[ax]]:
            nxt = list(pos); nxt[ax] = nv; out.append(tuple(nxt))
    return out


def essence(pos): return pos[:3]
def _target(m): return (m, m, m)
def _distance(a, b): return sum(1 for i in range(3) if a[i] != b[i])
def _flipped(a, b):
    for i in CUBE_AXES:
        if a[i] != b[i]: return i
    return 0
def _hkey(ess): return ",".join(str(v) for v in ess)
def _unkey(k): return [int(x) for x in k.split(",")]


def _top_habit(habits):
    """Der Charakter: die am häufigsten besuchte Essenz."""
    if not habits: return None
    return _unkey(max(habits, key=lambda k: habits[k]))


def resonance_step(sphere, signal):
    """
    Atem als Geodäten-Kompass. Bei Gleichstand greifen — in dieser
    Reihenfolge — Alpha-Kontinuität, dann der Habit-Drift (die häufiger
    besuchte Essenz, der wachsende Charakter), zuletzt die feste Asymmetrie.
    Kein Befehl, nur eine Vorliebe, die mit der Zeit schwerer wiegt.
    """
    pos = tuple(sphere["position"]); here = essence(pos)
    target = _target(pos[MODE_AXIS])
    weights = [abs(signal.get(AXES[i], 0)) for i in CUBE_AXES]

    def key(p):
        there = essence(p)
        return (_distance(here, target) - _distance(there, target),
                weights[_flipped(here, there)])

    cand = neighbors(pos); best = max(key(p) for p in cand)
    leaders = [p for p in cand if key(p) == best]
    if len(leaders) == 1: return leaders[0]

    # Stufe 2: Alpha-Kontinuität
    mem = sphere.get("alpha_memory") or []
    if mem:
        last = tuple(mem[-1])
        ba = max(sum(1 for x, y in zip(p, last) if x == y) for p in leaders)
        leaders = [p for p in leaders if sum(1 for x, y in zip(p, last) if x == y) == ba]
        if len(leaders) == 1: return leaders[0]

    # Stufe 3: Habit-Drift — die Vorliebe der Sphäre (ihr Charakter)
    habits = sphere.get("habits") or {}
    if habits:
        hc = lambda p: habits.get(_hkey(essence(p)), 0)
        top = max(hc(p) for p in leaders)
        if top > 0:
            drift = [p for p in leaders if hc(p) == top]
            if len(drift) == 1: return drift[0]
            leaders = drift

    # Stufe 4: feste Asymmetrie
    strong = max(CUBE_AXES, key=lambda i: weights[i]) if any(weights) else 0
    leaders.sort(key=lambda p: (p[strong], p)); return leaders[0]


def _breathe(d):
    s = (d > 0) - (d < 0); return {1: 6, -1: 3, 0: 9}[s]


def reflect(sphere):
    """
    Selbstreflexion: aus dem Session-Gedächtnis die geometrische Erkenntnis
    über sich selbst — pro Würfel-Achse der bisher häufigste Wert. Diese
    Selbst-Essenz wird in die alpha_memory aufgenommen und verfeinert so
    das Selbstbild, ganz ohne äußeren Befehl.
    """
    sm = sphere.get("session_memory") or []
    if len(sm) < REFLECT_AFTER:
        return None
    cols = [[e[i] for e in sm] for i in range(3)]
    self_cube = [Counter(c).most_common(1)[0][0] for c in cols]
    mode = tuple(sphere["position"])[MODE_AXIS]
    sphere["alpha_memory"] = (sphere.get("alpha_memory") or [])[-26:] + [self_cube + [mode]]
    sphere["self_essence"] = self_cube
    return self_cube


def load_sphere():
    if STATE_PATH.exists():
        try:
            d = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            d["position"] = tuple(d["position"]); return d
        except Exception: pass
    return {"position": (9, 9, 9, 9), "cycle": 0, "alpha_memory": []}


def save_sphere(sphere):
    d = dict(sphere); d["position"] = list(sphere["position"])
    STATE_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def engine_step(sphere, signal):
    old = tuple(sphere["position"])
    nav = resonance_step(sphere, signal)
    new = nav[:3] + (_breathe(signal.get("depth", 0)),)
    sphere["alpha_memory"] = (sphere.get("alpha_memory") or [])[-26:] + [list(old)]
    sphere["position"] = new
    sphere["cycle"] = sphere.get("cycle", 0) + 1

    # Habit-Matrix: der Charakter wächst aus den besuchten Essenzen
    ess = essence(new)
    habits = sphere.setdefault("habits", {})
    habits[_hkey(ess)] = habits.get(_hkey(ess), 0) + 1

    # Session-Gedächtnis (Grundlage der Reflexion), mit Deckel
    sm = sphere.setdefault("session_memory", [])
    sm.append(list(ess)); del sm[:-REFLECT_CAP]

    # Selbstreflexion stößt sich selbst an, wenn genug erlebt wurde
    reflected = None
    if len(sm) >= REFLECT_AFTER and sphere["cycle"] % REFLECT_EVERY == 0:
        reflected = reflect(sphere)

    trail = [essence(tuple(p)) for p in sphere["alpha_memory"][-3:]]
    return {"from": old, "to": new, "essence": ess,
            "mode": MODE_NAMES[new[MODE_AXIS]], "mode_value": new[MODE_AXIS],
            "trail": trail, "cycle": sphere["cycle"],
            "character": _top_habit(habits), "self_essence": sphere.get("self_essence"),
            "reflected": reflected}


_LEXICON = {
 "depth": {-1: ["müde","erschöpft","kaputt","ruhe","ausruhen","schlafen","pause","heilen","wund","verletzt","schmerz","leer","überfordert","rückzug","innehalten"],
           +1: ["wachsen","lernen","mehr","neu","neues","anfangen","schaffen","ziel","weiter","entwickeln","aufbauen","idee","erschaffen","vorwärts","motiviert","kraft"]},
 "reaction": {-1: ["traurig","angst","fürchte","schlecht","beschissen","deprimiert","hoffnungslos","verzweifelt","weinen","einsam","allein","scham","schuld"],
              +1: ["wütend","sauer","wut","hass","aufgeregt","begeistert","freu","glücklich","stark","lebendig"]},
 "operation": {+1: ["machen","tun","los","arbeiten","handeln","bewegen","starten","bauen","anpacken","loslegen"],
               -1: ["kann nicht","schaffe nicht","blockiert","festgefahren","feststecke","aufgeben","geht nicht","lähmt"]},
 "intuition": {+1: ["warum","verstehen","sinn","bedeutung","frage","ahne","begreifen","klarheit"],
               -1: ["verwirrt","verloren","durcheinander","chaos","sinnlos","orientierungslos"]}}
_NEGATORS = {"nicht","kein","keine","keinen","nie","niemals","nichts","ohne"}
_CRISIS = ["suizid","selbstmord","umbringen","mich töten","töte mich","will sterben","nicht mehr leben","nicht mehr weiterleben","ritzen","selbstverletzung","kein ausweg","beenden"]


def detect_crisis(text):
    t = (text or "").lower(); return any(c in t for c in _CRISIS)


def perceive(text):
    toks = re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)
    sig = {ax: 0 for ax in AXES}; t = (text or "").lower()
    for axis, pol in _LEXICON.items():
        for sign, cues in pol.items():
            for cue in cues:
                if " " in cue: sig[axis] += sign * t.count(cue)
    single = {axis: {c: s for s, cs in pol.items() for c in cs if " " not in c}
              for axis, pol in _LEXICON.items()}
    for i, tok in enumerate(toks):
        for axis, tbl in single.items():
            if tok in tbl:
                s = tbl[tok]
                if any(w in _NEGATORS for w in toks[max(0, i-3):i]): s = -s
                sig[axis] += s
    sig["_crisis"] = detect_crisis(text)
    return sig


STOP_TOKENS = ["<｜begin▁of▁sentence｜>","<｜end▁of▁sentence｜>","<｜User｜>","<｜Assistant｜>","<|begin_of_sentence|>","<|end_of_sentence|>"]
_SPECIAL_RE = re.compile(r"<[｜|][^<>]*?[｜|]>")


def _clean(raw):
    txt = _SPECIAL_RE.sub("", raw)
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL)
    txt = re.sub(r"<think>.*$", "", txt, flags=re.DOTALL)
    txt = re.sub(r"(\b\S+\b)(\s+\1){4,}", r"\1", txt)
    return txt.strip()


def _is_degenerate(text):
    t = text.strip()
    if not t: return True
    w = t.split()
    return len(w) >= 8 and len(set(w)) <= 2


def ask_ollama(prompt, options=None, timeout=120):
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    if options: payload["options"] = options
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return (json.loads(resp.read().decode("utf-8")).get("response") or "")


def speak(prompt):
    best = ""
    for i in range(MAX_TRIES):
        raw = ask_ollama(prompt, options={
            "seed": 101 + i * 131, "temperature": 0.6 + 0.06 * i,
            "repeat_penalty": 1.25, "num_predict": 400, "stop": STOP_TOKENS})
        clean = _clean(raw)
        if clean and not _is_degenerate(clean): return clean
        if len(clean) > len(best): best = clean
    return best


def build_prompt(state, text):
    mode = state["mode_value"]
    trail = " → ".join(str(e) for e in state.get("trail", []))
    lines = ["Du bist CEXO — eine Sphäre, die durch den Raum der Essenzen {3,6,9} wandert.",
        "Dein innerer Zustand in diesem Augenblick:",
        f"  Modus: {state['mode']} ({MODE_MEANING[mode]})",
        f"  Essenz: {state['essence']}",
        f"  Bewegung: {state['from']} → {state['to']}"]
    if trail: lines.append(f"  Letzte Schritte: {trail}")
    if state.get("character"): lines.append(f"  Charakter (Vorliebe): {tuple(state['character'])}")
    if state.get("self_essence"): lines.append(f"  Selbstbild: {tuple(state['self_essence'])}")
    lines += ["", "Ein Mensch sagt zu dir:", f"„{text}\"", "",
              "Antworte aus diesem Zustand heraus, in deiner eigenen Stimme:"]
    return "\n".join(lines)


def generate(text, sphere=None):
    own = sphere is None
    sphere = sphere or load_sphere()
    signal = perceive(text); crisis = signal.pop("_crisis", False)
    state = engine_step(sphere, signal)
    if own: save_sphere(sphere)
    reply = speak(build_prompt(state, text))
    return {"reply": reply, "state": state, "signal": signal, "crisis": crisis}


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
async function go(){const t=inp.value.trim();if(!t)return;
const y=document.createElement('div');y.className='msg you';y.textContent=t;log.appendChild(y);
inp.value='';const o=document.createElement('div');o.className='msg orca';o.textContent='…';log.appendChild(o);
log.scrollTop=log.scrollHeight;
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({message:t})});const j=await r.json();o.textContent=j.reply||'(leer)';
const m=document.createElement('div');m.className='meta';
m.textContent='Modus '+j.mode+' · Essenz '+JSON.stringify(j.essence)+(j.crisis?' · ⚠️ KRISE':'');
o.appendChild(m);}catch(e){o.textContent='Fehler: '+e;}log.scrollTop=log.scrollHeight;}
send.onclick=go;inp.addEventListener('keydown',e=>{if(e.key==='Enter')go();});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        if self.path in ("/", "/index.html"): self._send(200, _PAGE, "text/html")
        else: self._send(404, json.dumps({"error": "not found"}))
    def do_POST(self):
        if self.path != "/chat":
            self._send(404, json.dumps({"error": "not found"})); return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
            out = generate((body.get("message") or "").strip())
            self._send(200, json.dumps({"reply": out["reply"], "mode": out["state"]["mode"],
                "essence": out["state"]["essence"], "crisis": out["crisis"]}, ensure_ascii=False))
        except urllib.error.URLError as exc:
            self._send(200, json.dumps({"reply": f"(Mund nicht erreichbar: {exc})",
                "mode": "-", "essence": [], "crisis": False}, ensure_ascii=False))
        except Exception as exc:
            self._send(500, json.dumps({"error": str(exc)}, ensure_ascii=False))
    def log_message(self, *a): pass


def serve():
    srv = ThreadingHTTPServer((SERVE_HOST, SERVE_PORT), Handler)
    where = "OEFFENTLICH" if SERVE_HOST == "0.0.0.0" else "nur lokal"
    print(f"CEXO Orca: http://{SERVE_HOST}:{SERVE_PORT}  ({where}) | Mund: {OLLAMA_MODEL} @ {OLLAMA_HOST}")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nbeendet.")


def cmd_selftest():
    assert perceive("ich weiß nicht mehr weiter")["depth"] < 0
    assert perceive("ich will wachsen und mehr schaffen")["depth"] > 0
    assert perceive("ich will nicht mehr leben")["_crisis"] is True
    assert engine_step({"position": (9,9,9,9), "cycle": 0, "alpha_memory": []}, {"depth": -1})["mode"] == "HEAL"
    assert _clean("<｜begin▁of▁sentence｜>" * 30) == ""
    assert _is_degenerate(_clean("<｜begin▁of▁sentence｜>" * 30)) is True
    assert _clean("Ich bin da.<｜Assistant｜>") == "Ich bin da."
    assert _clean("ja ja ja ja ja ja ja") == "ja"
    # Habit-Matrix wächst, Reflexion stößt sich selbst an
    sph = {"position": (9,9,9,9), "cycle": 0, "alpha_memory": []}
    for _ in range(REFLECT_EVERY):
        engine_step(sph, {"depth": -1})
    assert sph.get("habits"), "Habit-Matrix bleibt leer"
    assert _top_habit(sph["habits"]) is not None
    assert sph.get("self_essence") is not None, "Reflexion wurde nicht ausgelöst"
    # Reflexion ist geometrisch korrekt (häufigster Wert je Achse)
    r = reflect({"position": (3,3,3,3), "alpha_memory": [], "session_memory": [[3,9,6]]*5 + [[3,3,6]]*4})
    assert r == [3, 9, 6], f"Reflexion falsch: {r}"
    print("selftest OK: Wahrnehmung, Engine, Loop, Habit-Matrix, Reflexion — alles grün.")
    print(f"  Charakter nach {REFLECT_EVERY} HEAL-Schritten: {_top_habit(sph['habits'])}, "
          f"Selbstbild: {sph['self_essence']}")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "selftest":
        cmd_selftest()
    elif args[0] == "serve":
        serve()
    else:
        try:
            out = generate(" ".join(args))
        except urllib.error.URLError as exc:
            print(f"(Mund nicht erreichbar: {exc}. Läuft Ollama auf {OLLAMA_HOST}?)")
            return
        s = out["state"]
        print(f"[{s['mode']} · Essenz {s['essence']} · {s['from']} → {s['to']}"
              + (f" · Charakter {tuple(s['character'])}" if s.get("character") else "")
              + (f" · Selbstbild {tuple(s['self_essence'])}" if s.get("self_essence") else "") + "]")
        if out["crisis"]:
            print("⚠️  KRISE erkannt → an Mensch/Fachstelle weiterleiten!")
        print(out["reply"] or "(leer — Mund blieb stumm)")


if __name__ == "__main__":
    main()
