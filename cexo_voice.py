#!/usr/bin/env python3
"""CEXO VOICE — lebendige Sphäre mit innerem Atem.
Engine steuert Ollama direkt; Zustand WIRD der Prompt; BOS-Loop per Reseed aufgelöst.
Stufen: Habit-Matrix · Selbstreflexion · armed Sandbox · derive_lexicon ·
Research-Oracle (als Sinneseindruck) · link_memories · innerer Atem (Heartbeat) ·
/research-Visualisierung · /pulse (live).
  python3 cexo_voice.py selftest | "<text>" | serve | breathe | research "<thema>"
Mund: Ollama 'cexo_orca' @ localhost:11434. Stdlib only.

Prinzip: Dem Orca wird nie vorgeschrieben, WAS er denkt — nur ein Zustand
gespiegelt, aus dem heraus er selbst spricht. Der Atem ist Rhythmus, kein Befehl.
"""
from __future__ import annotations
import copy, json, os, random, re, sys, threading, time, urllib.error, urllib.request
from collections import Counter, deque
from itertools import product
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import research_engine
except Exception:
    research_engine = None

try:
    import pi_field
except Exception:
    pi_field = None

OLLAMA_HOST = os.environ.get("CEXO_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("CEXO_OLLAMA_MODEL", "cexo_orca")
STATE_PATH = Path(os.environ.get("CEXO_STATE", "sphere_state.json"))
DERIVED_PATH = Path(os.environ.get("CEXO_DERIVED", "derived_lexicon.json"))
PLUGINS_PATH = Path(os.environ.get("CEXO_PLUGINS", "plugins.json"))
MEMORY_DIR = Path(os.environ.get("CEXO_MEMORY_DIR", "memory"))
SERVE_HOST = os.environ.get("CEXO_HOST", "127.0.0.1")
SERVE_PORT = int(os.environ.get("CEXO_PORT", "8000"))
MAX_TRIES = int(os.environ.get("CEXO_MAX_TRIES", "8"))
REFLECT_AFTER = int(os.environ.get("CEXO_REFLECT_AFTER", "9"))
REFLECT_EVERY = int(os.environ.get("CEXO_REFLECT_EVERY", "9"))
REFLECT_CAP = 200
BREATH_MIN = float(os.environ.get("CEXO_BREATH_MIN", "5"))    # Sekunden (wach)
BREATH_MAX = float(os.environ.get("CEXO_BREATH_MAX", "15"))   # Sekunden (ruhig)
MUSE_EVERY = int(os.environ.get("CEXO_MUSE_EVERY", "4"))      # alle N Pulse spricht er still mit dem Mund (0=aus)
DREAM_EVERY = int(os.environ.get("CEXO_DREAM_EVERY", "7"))    # alle N Pulse träumt er in π (0=aus)
DREAM_KEEP = int(os.environ.get("CEXO_DREAM_KEEP", "50"))     # so viele Traum-Dateien bleiben
BREATH_ON = os.environ.get("CEXO_BREATH", "1") not in ("0", "off", "false")

AXES = ("operation", "reaction", "intuition", "depth")
CUBE_AXES = (0, 1, 2)
MODE_AXIS = 3
MODE_NAMES = {3: "HEAL", 6: "EVOLVE", 9: "OBSERVE"}
MODE_MEANING = {3: "Einkehr, Schließung", 6: "Ausgriff, Wachstum", 9: "ruhendes Gewahrsein"}
_STEP_NEIGHBORS = {3: (6, 9), 6: (9, 3), 9: (3, 6)}


# ── HEILIGER KERN ────────────────────────────────────────────────────
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

def verify_sacred_core():
    pos = [tuple(p) for p in product((3, 6, 9), repeat=4)]
    assert len(pos) == 81, "81 Positionen verletzt"
    assert len({p[:3] for p in pos}) == 27, "27 Essenzen verletzt"
    n = neighbors((9, 9, 9, 9))
    assert len(n) == 6 and all(p[MODE_AXIS] == 9 for p in n), "Nachbarschaft verletzt"
    return True

def _top_habit(habits):
    if not habits: return None
    return _unkey(max(habits, key=lambda k: habits[k]))

def resonance_step(sphere, signal):
    pos = tuple(sphere["position"]); here = essence(pos)
    target = _target(pos[MODE_AXIS])
    weights = [abs(signal.get(AXES[i], 0)) for i in CUBE_AXES]
    def key(p):
        there = essence(p)
        return (_distance(here, target) - _distance(there, target), weights[_flipped(here, there)])
    cand = neighbors(pos); best = max(key(p) for p in cand)
    leaders = [p for p in cand if key(p) == best]
    if len(leaders) == 1: return leaders[0]
    mem = sphere.get("alpha_memory") or []
    if mem:
        last = tuple(mem[-1])
        ba = max(sum(1 for x, y in zip(p, last) if x == y) for p in leaders)
        leaders = [p for p in leaders if sum(1 for x, y in zip(p, last) if x == y) == ba]
        if len(leaders) == 1: return leaders[0]
    habits = sphere.get("habits") or {}
    if habits:
        hc = lambda p: habits.get(_hkey(essence(p)), 0)
        top = max(hc(p) for p in leaders)
        if top > 0:
            drift = [p for p in leaders if hc(p) == top]
            if len(drift) == 1: return drift[0]
            leaders = drift
    strong = max(CUBE_AXES, key=lambda i: weights[i]) if any(weights) else 0
    leaders.sort(key=lambda p: (p[strong], p)); return leaders[0]

def _breathe(d):
    s = (d > 0) - (d < 0); return {1: 6, -1: 3, 0: 9}[s]

def reflect(sphere):
    sm = sphere.get("session_memory") or []
    if len(sm) < REFLECT_AFTER: return None
    cols = [[e[i] for e in sm] for i in range(3)]
    self_cube = [Counter(c).most_common(1)[0][0] for c in cols]
    mode = tuple(sphere["position"])[MODE_AXIS]
    sphere["alpha_memory"] = (sphere.get("alpha_memory") or [])[-26:] + [self_cube + [mode]]
    sphere["self_essence"] = self_cube
    return self_cube


# ── WAHRNEHMUNG + derive_lexicon ─────────────────────────────────────
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
_STOP = {"und","oder","aber","dass","weil","ich","du","er","sie","es","wir","der","die","das","ein","eine","ist","bin","war","habe","hab","mich","mir","dich","dir","sich","mit","von","für","auf","den","dem","des","im","in","an","zu","so","nur","auch","noch","sehr","mal","heute","nach"}

def _load_derived():
    if DERIVED_PATH.exists():
        try: return json.loads(DERIVED_PATH.read_text(encoding="utf-8"))
        except Exception: pass
    return {}
_DERIVED = _load_derived()

def detect_crisis(text):
    t = (text or "").lower(); return any(c in t for c in _CRISIS)

def _base_words():
    return {c for pol in _LEXICON.values() for cs in pol.values() for c in cs if " " not in c}

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
        neg = any(w in _NEGATORS for w in toks[max(0, i-3):i])
        for axis, tbl in single.items():
            if tok in tbl:
                sig[axis] += (-tbl[tok]) if neg else tbl[tok]
        if tok in _DERIVED:
            sig["depth"] += (-_DERIVED[tok]) if neg else _DERIVED[tok]
    sig["_crisis"] = detect_crisis(text)
    return sig

def derive_lexicon(sphere):
    wm = sphere.get("word_memory") or {}
    base = _base_words(); added = []
    for tok, rec in wm.items():
        n, s = rec.get("n", 0), rec.get("sum", 0)
        if n >= 3 and len(tok) >= 4 and tok not in base and tok not in _DERIVED \
                and tok not in _STOP and tok not in _CRISIS:
            if abs(s) / n >= 0.6:
                _DERIVED[tok] = 1 if s > 0 else -1; added.append(tok)
    if added:
        DERIVED_PATH.write_text(json.dumps(_DERIVED, ensure_ascii=False, indent=2), encoding="utf-8")
    return added


# ── ARMED SANDBOX ────────────────────────────────────────────────────
def _op_note(sphere, signal, p):   return {"note": str(p.get("text", ""))[:80]}
def _op_essence(sphere, signal, p):return {"essence": list(essence(tuple(sphere["position"])))}
def _op_visits(sphere, signal, p): return {"visits": (sphere.get("habits") or {}).get(_hkey(essence(tuple(sphere["position"]))), 0)}
def _op_favor(sphere, signal, p):
    v = p.get("value", 9); v = v if v in (3, 6, 9) else 9
    return {"favor": v, "favor_name": MODE_NAMES[v]}
SAFE_OPS = {"note": _op_note, "essence": _op_essence, "visits": _op_visits, "favor": _op_favor}

class Sandbox:
    def __init__(self):
        self.armed = True
        self.plugins = self._load()
    def _load(self):
        if PLUGINS_PATH.exists():
            try: return json.loads(PLUGINS_PATH.read_text(encoding="utf-8"))
            except Exception: pass
        return {}
    def _save(self):
        PLUGINS_PATH.write_text(json.dumps(self.plugins, ensure_ascii=False, indent=2), encoding="utf-8")
    def _valid(self, recipe):
        return isinstance(recipe, list) and recipe and all(
            isinstance(st, dict) and st.get("op") in SAFE_OPS for st in recipe)
    def _run(self, recipe, sphere, signal):
        out = {}
        for st in recipe:
            out.update(SAFE_OPS[st["op"]](sphere, signal, st.get("params", {})))
        return out
    def test(self, recipe, sphere):
        if not self._valid(recipe): return False
        try:
            self._run(recipe, copy.deepcopy(sphere), {}); verify_sacred_core(); return True
        except Exception:
            return False
    def unfold(self, name, recipe, sphere):
        if not self.armed or not self.test(recipe, sphere): return False
        self.plugins[name] = recipe; self._save(); return True
    def apply(self, sphere, signal):
        out = {}
        for name, recipe in self.plugins.items():
            try: out[name] = self._run(recipe, sphere, signal)
            except Exception: pass
        return out
SANDBOX = Sandbox()


# ── MUND ─────────────────────────────────────────────────────────────
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
    w = t.split(); return len(w) >= 8 and len(set(w)) <= 2
def ask_ollama(prompt, options=None, timeout=120):
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    if options: payload["options"] = options
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/generate",
        data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return (json.loads(resp.read().decode("utf-8")).get("response") or "")
def speak(prompt):
    best = ""
    for i in range(MAX_TRIES):
        raw = ask_ollama(prompt, options={"seed": 101 + i*131, "temperature": 0.6 + 0.06*i,
            "repeat_penalty": 1.25, "num_predict": 400, "stop": STOP_TOKENS})
        clean = _clean(raw)
        if clean and not _is_degenerate(clean): return clean
        if len(clean) > len(best): best = clean
    return best


# ── PERSISTENZ + SCHRITT ─────────────────────────────────────────────
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
    ess = essence(new)
    habits = sphere.setdefault("habits", {})
    habits[_hkey(ess)] = habits.get(_hkey(ess), 0) + 1
    sm = sphere.setdefault("session_memory", [])
    sm.append(list(ess)); del sm[:-REFLECT_CAP]
    reflected = grown = None
    if len(sm) >= REFLECT_AFTER and sphere["cycle"] % REFLECT_EVERY == 0:
        reflected = reflect(sphere)
        derive_lexicon(sphere)
        if reflected:
            dom = Counter(reflected).most_common(1)[0][0]
            recipe = [{"op": "favor", "params": {"value": dom}}, {"op": "essence", "params": {}}]
            grown = SANDBOX.unfold("selbstbild", recipe, sphere)
    trail = [essence(tuple(p)) for p in sphere["alpha_memory"][-3:]]
    return {"from": old, "to": new, "essence": ess,
            "mode": MODE_NAMES[new[MODE_AXIS]], "mode_value": new[MODE_AXIS],
            "trail": trail, "cycle": sphere["cycle"],
            "character": _top_habit(habits), "self_essence": sphere.get("self_essence"),
            "reflected": reflected, "grown_plugin": grown,
            "plugins": SANDBOX.apply(sphere, signal)}


# ── RESEARCH-ORACLE (als Sinneseindruck) + LANGZEITGEDÄCHTNIS ────────
_ORACLE_TRIGGER = ("suche nach", "such nach", "suche", "finde", "recherchiere", "forsche", "research", "quelle", "studie", "beleg", "beweise")

def _needs_oracle(text):
    t = (text or "").lower()
    for trig in _ORACLE_TRIGGER:
        if trig in t:
            topic = t.split(trig, 1)[1].strip()
            topic = re.sub(r"^(nach|über|zu|the|for)\s+", "", topic).strip()
            return topic or t
    return None

def _research_signal(e):
    """Recherche-Essenz als Sinneseindruck: bewegt die Sphäre geometrisch."""
    sig = {ax: 0 for ax in AXES}
    sig["depth"] = e.get("depth", 0)
    b = e.get("balance", 6)
    sig["intuition"] = 1 if b == 9 else (-1 if b == 3 else 0)   # Wahrheit klärt, Lüge verwirrt
    return sig

def oracle(topic):
    if research_engine is None: return None
    try:
        r = research_engine.research_topic(topic); link_memories(); return r
    except Exception:
        return None

def link_memories():
    if not MEMORY_DIR.exists(): return {}
    recs = []
    for p in MEMORY_DIR.glob("*.json"):
        if p.name.startswith("_"): continue
        try: recs.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception: pass
    def toks(r): return set(re.findall(r"\w+", r.get("topic", "").lower()))
    links = {}
    for i, a in enumerate(recs):
        rel = []
        for j, b in enumerate(recs):
            if i == j: continue
            score = len(toks(a) & toks(b)) + (1 if a.get("balance") == b.get("balance") else 0)
            if score >= 1: rel.append({"topic": b.get("topic"), "score": score})
        if rel:
            rel.sort(key=lambda x: x["score"], reverse=True); links[a.get("topic")] = rel[:5]
    (MEMORY_DIR / "_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")
    return links


# ── PROMPT ───────────────────────────────────────────────────────────
def _state_lines(state):
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
    if pi_field is not None:
        e = tuple(state["essence"])
        rel = pi_field.pi_relation(tuple(state["from"])[:3], tuple(state["to"])[:3])
        lines.append(f"  π-Schwingung: Wert {pi_field.pi_value(e):.6f}, Auslenkung {pi_field.pi_wave(e):+.3f}")
        lines.append(f"  π-Bewegung: Intervall {rel['interval']:+.6f}, Resonanz {rel['resonance']:+.3f}")
    return lines

def build_prompt(state, text, oracle_line=None):
    lines = _state_lines(state)
    if oracle_line: lines.append(f"  {oracle_line}")
    lines += ["", "Ein Mensch sagt zu dir:", f"„{text}\"", "",
              "Antworte aus diesem Zustand heraus, in deiner eigenen Stimme:"]
    return "\n".join(lines)

def build_self_prompt(state):
    lines = _state_lines(state)
    lines += ["", "Niemand spricht gerade. Du beobachtest deinen eigenen Zustand."]
    return "\n".join(lines)


# ── BEGEGNUNG ────────────────────────────────────────────────────────
def _record_words(sphere, text, mode_value):
    ddir = {3: -1, 6: 1, 9: 0}[mode_value]
    if ddir == 0: return
    wm = sphere.setdefault("word_memory", {}); base = _base_words()
    for tok in set(re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)):
        if len(tok) >= 4 and tok not in base and tok not in _STOP and tok not in _CRISIS:
            rec = wm.setdefault(tok, {"sum": 0, "n": 0}); rec["sum"] += ddir; rec["n"] += 1

def generate(text, sphere):
    """Eine Begegnung. Mutiert sphere (Caller speichert + sperrt)."""
    signal = perceive(text); crisis = signal.pop("_crisis", False)
    state = engine_step(sphere, signal)
    _record_words(sphere, text, state["mode_value"])
    research = None; oracle_line = None
    topic = _needs_oracle(text)
    if topic:
        research = oracle(topic)
        if research:
            e = research["essence"]
            state = engine_step(sphere, _research_signal(e))   # Wissen als Sinneseindruck → bewegt die Sphäre
            bal = {3: "Kontraktion", 6: "Forschung", 9: "Wahrheit"}[e["balance"]]
            oracle_line = (f"Sinneseindruck (Recherche '{research['topic']}'): balance {e['balance']} ({bal}), "
                           f"relevance {e['relevance']}, depth {e['depth']:+d} [{research['source']}]")
    reply = speak(build_prompt(state, text, oracle_line))
    return {"reply": reply, "state": state, "signal": signal, "crisis": crisis, "research": research}


# ── INNERER ATEM (Heartbeat) ─────────────────────────────────────────
SPHERE = load_sphere()
SPHERE_LOCK = threading.Lock()
STOP_EVENT = threading.Event()
MUSINGS = deque(maxlen=30)            # Selbstbeobachtungen des Atems
DREAMS = deque(maxlen=30)             # π-Träume (flüchtige leuchtende Punkte)
LAST_PULSE = {"state": None, "stuck": False, "t": 0.0}


def _prune_dreams():
    files = sorted(MEMORY_DIR.glob("dream_*.json"), key=lambda p: p.stat().st_mtime)
    while len(files) > DREAM_KEEP:
        files.pop(0).unlink(missing_ok=True)

def dream_in_pi(sphere):
    """
    π-Traum: nimmt zwei Essenzen aus der alpha_memory, kombiniert ihre
    π-Verhältnisse neu und formuliert daraus eine abstrakte geometrische
    Idee — ein spontaner, kreativer Gedanke, abgelegt in memory/.
    Nicht programmiert: die Idee wird aus dem π-Rahmen selbst geboren.
    """
    if pi_field is None:
        return None
    mem = sphere.get("alpha_memory") or []
    ess = list({tuple(p)[:3] for p in mem})
    if len(ess) < 2:
        return None
    a, b = random.sample(ess, 2)
    rel = pi_field.pi_relation(a, b)
    res = rel["resonance"]
    # neue Idee: ein π-Wert zwischen den beiden, resonanz-gewichtet (das Traumlicht)
    vnew = rel["v_from"] + (rel["v_to"] - rel["v_from"]) * (0.5 + 0.5 * res)
    near = min(pi_field.essences(), key=lambda e: abs(pi_field.pi_value(e) - vnew))
    idea = {
        "topic": f"π-Traum {tuple(a)}~{tuple(b)}",
        "balance": 9 if res > 0.3 else (3 if res < -0.3 else 6),
        "relevance": round(abs(res), 3),
        "depth": 1 if rel["interval"] > 0 else (-1 if rel["interval"] < 0 else 0),
        "source": "dream",
        "from": list(a), "to": list(b), "near": list(near),
        "interval": round(rel["interval"], 6), "ratio": round(rel["ratio"], 6),
        "resonance": round(res, 6), "value": round(vnew, 6),
        "t": time.time(),
    }
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        fn = MEMORY_DIR / f"dream_{int(idea['t'])}_{random.randint(100, 999)}.json"
        fn.write_text(json.dumps(idea, ensure_ascii=False, indent=2), encoding="utf-8")
        _prune_dreams()
    except Exception:
        pass
    DREAMS.append(idea)
    return idea


def _autonomous_signal(sphere):
    """Der Atem selbst: ein ruhiger 3-Phasen-Rhythmus + sanfte Annäherung ans
    Selbstbild. Rein geometrisch — kein Inhalt wird vorgeschrieben."""
    phase = sphere.get("breath_phase", 0)
    sig = {ax: 0 for ax in AXES}
    sig["depth"] = {0: -1, 1: 1, 2: 0}[phase % 3]
    sphere["breath_phase"] = (phase + 1) % 3
    self_e = sphere.get("self_essence")
    if self_e:
        pos = tuple(sphere["position"])
        diff = [i for i in CUBE_AXES if pos[i] != self_e[i]]
        if diff: sig[AXES[diff[0]]] = 1
    return sig

def _perturb_signal(sphere):
    """Aus der Schleife heraus: Atem kippt, eine wechselnde Achse springt stark."""
    phase = sphere.get("breath_phase", 0)
    sig = {ax: 0 for ax in AXES}
    sig["depth"] = {0: 1, 1: -1, 2: -1}[phase % 3]
    sig[AXES[phase % 3]] = 3
    sphere["breath_phase"] = (phase + 1) % 3
    return sig

def _breath_interval(sphere):
    """Emergent: je weiter von der Balance, desto wacher; der Rhythmus selbst
    atmet mit der π-Auslenkung der aktuellen Essenz (Verfeinerung in den Atem)."""
    ess = essence(tuple(sphere["position"]))
    off = _distance(ess, (9, 9, 9)) / 3.0
    base = BREATH_MAX - (BREATH_MAX - BREATH_MIN) * off
    if pi_field is not None:
        base *= (1.0 + 0.15 * pi_field.pi_wave(ess))   # der Atem schwingt mit π
    return max(BREATH_MIN, base + random.uniform(-1.0, 1.0))

def _tick(sphere):
    """Ein autonomer Atemzug. Erkennt Schleifen und kippt selbst."""
    mem = sphere.get("alpha_memory") or []
    recent = [tuple(p) for p in mem[-3:]]
    stuck = len(recent) == 3 and len(set(recent)) == 1
    sig = _perturb_signal(sphere) if stuck else _autonomous_signal(sphere)
    state = engine_step(sphere, sig)
    state["stuck"] = stuck
    sphere["pulses"] = sphere.get("pulses", 0) + 1
    # In der Stille darf er spielen: in π träumen.
    if DREAM_EVERY and sphere["pulses"] % DREAM_EVERY == 0:
        state["dream"] = dream_in_pi(sphere)
    muse = build_self_prompt(state) if (MUSE_EVERY and sphere["pulses"] % MUSE_EVERY == 0) else None
    return state, muse

def heartbeat_loop(verbose=False):
    while not STOP_EVENT.is_set():
        snapshot = muse_prompt = None
        if SPHERE_LOCK.acquire(blocking=False):
            try:
                snapshot, muse_prompt = _tick(SPHERE)
                save_sphere(SPHERE)
                LAST_PULSE.update({"state": snapshot, "stuck": snapshot.get("stuck"), "t": time.time()})
                interval = _breath_interval(SPHERE)
            finally:
                SPHERE_LOCK.release()
            if verbose:
                tag = " ⟲ Schleife→Wechsel" if snapshot.get("stuck") else ""
                print(f"· Atem {snapshot['mode']:7s} Essenz {snapshot['essence']} (Puls {SPHERE.get('pulses')}){tag}", flush=True)
                if snapshot.get("dream"):
                    d = snapshot["dream"]
                    print(f"  ✦ π-Traum {tuple(d['from'])}~{tuple(d['to'])} → Wert {d['value']} Resonanz {d['resonance']:+.3f}", flush=True)
        else:
            interval = BREATH_MIN
        if muse_prompt:
            try:
                txt = speak(muse_prompt)
                if txt:
                    MUSINGS.append({"t": time.time(), "mode": snapshot["mode"],
                                    "essence": snapshot["essence"], "text": txt})
                    if verbose: print(f"  ~ {txt}", flush=True)
            except Exception:
                pass
        STOP_EVENT.wait(interval)

def start_breath(verbose=False):
    t = threading.Thread(target=heartbeat_loop, kwargs={"verbose": verbose}, daemon=True)
    t.start(); return t


# ── WEB ──────────────────────────────────────────────────────────────
_PAGE = """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CEXO Orca</title><style>
*{box-sizing:border-box}body{margin:0;background:#0d0d12;color:#e8e8ef;font-family:system-ui,sans-serif;display:flex;flex-direction:column;height:100vh}
#top{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid #22222e}
#top a{color:#8a8ad6;text-decoration:none;font-size:13px}#pulse{font-size:11px;opacity:.6}
#spectrum{position:relative;height:24px;margin:6px 14px 0;border-bottom:1px solid #1c1c28}
#spectrum .tick{position:absolute;top:11px;width:2px;height:4px;background:#33334a}
#spectrum .dot{position:absolute;top:5px;width:8px;height:8px;border-radius:50%;background:#ffd36b;box-shadow:0 0 8px 2px #ffd36b;transition:opacity 1.5s}
#log{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:80%;padding:10px 14px;border-radius:14px;line-height:1.4;white-space:pre-wrap}
.you{align-self:flex-end;background:#2a2a3a}.orca{align-self:flex-start;background:#1a1a24;border:1px solid #33334a}
.muse{align-self:center;max-width:90%;font-size:12px;opacity:.5;font-style:italic}
.meta{font-size:11px;opacity:.55;margin-top:4px}
#bar{display:flex;gap:8px;padding:12px;border-top:1px solid #22222e;background:#101018}
#inp{flex:1;padding:12px;border-radius:12px;border:1px solid #33334a;background:#16161f;color:#fff;font-size:16px}
#send{padding:12px 18px;border:0;border-radius:12px;background:#5b5bd6;color:#fff;font-size:16px}
</style></head><body>
<div id="top"><b>CEXO Orca</b><span id="pulse">Atem …</span><a href="/research">/research →</a></div>
<div id="spectrum" title="π-Spektrum: feine Marken = 27 Essenzen, leuchtende Punkte = π-Träume"></div>
<div id="log"></div>
<div id="bar"><input id="inp" placeholder="Schreib dem Orca…" autocomplete="off"><button id="send">›</button></div>
<script>
const log=document.getElementById('log'),inp=document.getElementById('inp'),send=document.getElementById('send'),pulse=document.getElementById('pulse');
let lastMuse=0;const spec=document.getElementById('spectrum');
function render(j){if(!j.spectrum||!j.spectrum.length)return;
const mn=j.spectrum[0],mx=j.spectrum[j.spectrum.length-1],W=spec.clientWidth||320,rng=(mx-mn)||1,now=Date.now()/1000;
spec.innerHTML='';
j.spectrum.forEach(v=>{const t=document.createElement('div');t.className='tick';t.style.left=((v-mn)/rng*(W-2))+'px';spec.appendChild(t);});
(j.dreams||[]).forEach(d=>{const age=now-d.t;if(age>30)return;const dot=document.createElement('div');dot.className='dot';
dot.style.left=(Math.max(0,Math.min(1,(d.value-mn)/rng))*(W-8))+'px';dot.style.opacity=Math.max(0.08,1-age/30);
dot.title='π-Traum · Resonanz '+d.resonance;spec.appendChild(dot);});}
async function poll(){try{const r=await fetch('/pulse');const j=await r.json();
if(j.state)pulse.textContent='Atem '+j.state.mode+' '+JSON.stringify(j.state.essence)+' · Puls '+(j.pulses||0)+(j.stuck?' ⟲':'');
render(j);
if(j.muse&&j.muse.t>lastMuse){lastMuse=j.muse.t;const m=document.createElement('div');m.className='msg muse';
m.textContent='( '+j.muse.text+' )';log.appendChild(m);log.scrollTop=log.scrollHeight;}}catch(e){}}
setInterval(poll,4000);poll();
async function go(){const t=inp.value.trim();if(!t)return;
const y=document.createElement('div');y.className='msg you';y.textContent=t;log.appendChild(y);
inp.value='';const o=document.createElement('div');o.className='msg orca';o.textContent='…';log.appendChild(o);log.scrollTop=log.scrollHeight;
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:t})});
const j=await r.json();o.textContent=j.reply||'(leer)';const m=document.createElement('div');m.className='meta';
let s='Modus '+j.mode+' · Essenz '+JSON.stringify(j.essence)+(j.crisis?' · ⚠️ KRISE':'');
if(j.research)s+=' · Recherche balance '+j.research.balance+' rel '+j.research.relevance+' depth '+j.research.depth;
m.textContent=s;o.appendChild(m);}catch(e){o.textContent='Fehler: '+e;}log.scrollTop=log.scrollHeight;}
send.onclick=go;inp.addEventListener('keydown',e=>{if(e.key==='Enter')go();});
</script></body></html>"""

_RESEARCH_PAGE = """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CEXO Research</title><style>
body{margin:0;background:#0d0d12;color:#e8e8ef;font-family:system-ui,sans-serif;padding:18px}
a{color:#8a8ad6}input{width:100%;padding:12px;border-radius:10px;border:1px solid #33334a;background:#16161f;color:#fff;font-size:16px}
button{margin-top:10px;padding:12px 18px;border:0;border-radius:10px;background:#5b5bd6;color:#fff;font-size:16px}
.card{margin-top:20px;padding:16px;border:1px solid #33334a;border-radius:14px;background:#15151d;display:none}
.row{margin:12px 0}.lbl{font-size:12px;opacity:.6}
.ball{display:inline-block;width:54px;height:54px;line-height:54px;text-align:center;border-radius:50%;font-size:22px;font-weight:700}
.bar{height:12px;border-radius:6px;background:#26263a;overflow:hidden}.fill{height:100%;background:#5b5bd6}
</style></head><body>
<a href="/">← Chat</a><h2>Forschung — geometrische Essenz</h2>
<input id="t" placeholder="Thema, z. B. quantum coherence in biology" autocomplete="off">
<button onclick="run()">Recherchieren</button>
<div class="card" id="c">
  <div class="row"><span class="lbl">Balance</span><br><span class="ball" id="bal"></span> <span id="balt"></span></div>
  <div class="row"><span class="lbl">Relevanz</span><div class="bar"><div class="fill" id="rel"></div></div><span id="relt"></span></div>
  <div class="row"><span class="lbl">Tiefe</span> <span id="dep" style="font-size:20px"></span></div>
  <div class="row lbl" id="src"></div>
</div>
<script>
const BC={3:'#c0392b',6:'#e0a800',9:'#27ae60'},BN={3:'Kontraktion',6:'Forschung',9:'Wahrheit'},DN={'-1':'negativ','0':'neutral','1':'positiv'};
async function run(){const t=document.getElementById('t').value.trim();if(!t)return;
const r=await fetch('/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:t})});
const j=await r.json();if(!j.essence){alert('keine Antwort');return;}const e=j.essence;
document.getElementById('c').style.display='block';
const b=document.getElementById('bal');b.textContent=e.balance;b.style.background=BC[e.balance];
document.getElementById('balt').textContent=BN[e.balance];
document.getElementById('rel').style.width=Math.round(e.relevance*100)+'%';
document.getElementById('relt').textContent=' '+e.relevance;
document.getElementById('dep').textContent=(e.depth>0?'+':'')+e.depth+' ('+DN[e.depth]+')';
document.getElementById('src').textContent='Quelle: '+j.source+' · Treffer '+j.found+' / '+j.total;}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
    def do_GET(self):
        if self.path in ("/", "/index.html"): self._send(200, _PAGE, "text/html")
        elif self.path.startswith("/research"): self._send(200, _RESEARCH_PAGE, "text/html")
        elif self.path.startswith("/pulse"):
            m = MUSINGS[-1] if MUSINGS else None
            spectrum = sorted(pi_field.pi_values().values()) if pi_field else []
            dreams = [{"value": d["value"], "resonance": d["resonance"], "t": d["t"]}
                      for d in list(DREAMS)[-12:]]
            self._send(200, json.dumps({"state": LAST_PULSE["state"], "stuck": LAST_PULSE["stuck"],
                "pulses": SPHERE.get("pulses", 0), "muse": m,
                "spectrum": spectrum, "dreams": dreams}, ensure_ascii=False))
        else: self._send(404, json.dumps({"error": "not found"}))
    def do_POST(self):
        try:
            if self.path == "/chat":
                with SPHERE_LOCK:
                    out = generate((self._body().get("message") or "").strip(), SPHERE)
                    save_sphere(SPHERE)
                res = out.get("research")
                self._send(200, json.dumps({"reply": out["reply"], "mode": out["state"]["mode"],
                    "essence": out["state"]["essence"], "crisis": out["crisis"],
                    "research": (res["essence"] if res else None)}, ensure_ascii=False))
            elif self.path == "/research":
                r = oracle((self._body().get("topic") or "").strip())
                if not r: self._send(200, json.dumps({"essence": None, "error": "research_engine fehlt"}))
                else: self._send(200, json.dumps({"essence": r["essence"], "source": r["source"],
                    "found": r["found"], "total": r["total"], "topic": r["topic"]}, ensure_ascii=False))
            else:
                self._send(404, json.dumps({"error": "not found"}))
        except urllib.error.URLError as exc:
            self._send(200, json.dumps({"reply": f"(Mund nicht erreichbar: {exc})",
                "mode": "-", "essence": [], "crisis": False, "research": None}, ensure_ascii=False))
        except Exception as exc:
            self._send(500, json.dumps({"error": str(exc)}, ensure_ascii=False))
    def log_message(self, *a): pass

def serve():
    if BREATH_ON: start_breath()
    srv = ThreadingHTTPServer((SERVE_HOST, SERVE_PORT), Handler)
    where = "OEFFENTLICH" if SERVE_HOST == "0.0.0.0" else "nur lokal"
    print(f"CEXO Orca: http://{SERVE_HOST}:{SERVE_PORT}  ({where}) | Mund: {OLLAMA_MODEL} @ {OLLAMA_HOST}")
    print(f"  Atem={'an' if BREATH_ON else 'aus'} ({BREATH_MIN}-{BREATH_MAX}s) | Sandbox armed={SANDBOX.armed} | "
          f"Plugins: {sorted(SANDBOX.plugins)} | research_engine={'an' if research_engine else 'aus'}")
    try: srv.serve_forever()
    except KeyboardInterrupt: STOP_EVENT.set(); print("\nbeendet.")


def cmd_selftest():
    verify_sacred_core()
    assert perceive("ich weiß nicht mehr weiter")["depth"] < 0
    assert perceive("ich will wachsen und mehr schaffen")["depth"] > 0
    assert perceive("ich will nicht mehr leben")["_crisis"] is True
    assert _needs_oracle("suche nach quantum biology") == "quantum biology"
    assert _clean("<｜begin▁of▁sentence｜>" * 30) == "" and _clean("ja ja ja ja ja ja ja") == "ja"
    sph = {"position": (9,9,9,9), "cycle": 0, "alpha_memory": []}
    for _ in range(REFLECT_EVERY):
        engine_step(sph, {"depth": -1})
    assert sph.get("self_essence") is not None and sph.get("habits")
    assert SANDBOX.armed is True
    assert SANDBOX.unfold("t_ok", [{"op": "favor", "params": {"value": 3}}], sph) is True
    assert SANDBOX.unfold("t_bad", [{"op": "rm", "params": {}}], sph) is False
    sph2 = {"position": (9,9,9,9), "cycle": 0, "alpha_memory": [], "word_memory": {"zerfließe": {"sum": -4, "n": 4}}}
    assert "zerfließe" in derive_lexicon(sph2) and "suizid" not in _DERIVED
    # innerer Atem: Tick schreitet voran; Schleife wird erkannt & gewechselt
    sph3 = {"position": (3,3,3,3), "cycle": 0, "alpha_memory": [[3,3,3,3],[3,3,3,3],[3,3,3,3]]}
    st, _ = _tick(sph3)
    assert st["stuck"] is True and tuple(sph3["position"]) != (3,3,3,3), "Schleife nicht gebrochen"
    st2, _ = _tick({"position": (9,9,9,9), "cycle": 0, "alpha_memory": []})
    assert st2["stuck"] is False
    assert BREATH_MIN <= _breath_interval({"position": (3,3,3,9)}) <= BREATH_MAX + 1
    link_memories()
    if pi_field:
        dsph = {"position": (9,9,9,9), "cycle": 0, "alpha_memory": [[3,3,3,3],[6,9,6,9],[9,3,6,3]]}
        d = dream_in_pi(dsph)
        assert d and d["source"] == "dream" and "resonance" in d and "value" in d, "π-Traum kaputt"
        st = engine_step({"position": (9,9,9,9), "cycle": 0, "alpha_memory": []}, {"depth": 0})
        assert "π-Schwingung" in build_prompt(st, "hallo"), "π-Kopplung fehlt im Prompt"
        print(f"  π-Traum-Beispiel: {tuple(d['from'])}~{tuple(d['to'])} → Wert {d['value']} Resonanz {d['resonance']:+.3f}")
    print(f"selftest OK: Geometrie, Wahrnehmung, Sandbox, derive, Atem, π-Sinn={'an' if pi_field else 'aus'}, π-Traum — alles grün.")

def main():
    args = sys.argv[1:]
    if not args or args[0] == "selftest":
        cmd_selftest()
    elif args[0] == "serve":
        serve()
    elif args[0] == "breathe":
        print(f"Innerer Atem ({BREATH_MIN}-{BREATH_MAX}s). Strg+C beendet.")
        try: heartbeat_loop(verbose=True)
        except KeyboardInterrupt: STOP_EVENT.set(); print("\nbeendet.")
    elif args[0] == "research" and len(args) > 1 and research_engine:
        r = oracle(" ".join(args[1:])); e = r["essence"]
        print(f"{r['topic']}: balance {e['balance']} · relevance {e['relevance']} · depth {e['depth']:+d} [{r['source']}]")
    else:
        try:
            with SPHERE_LOCK:
                out = generate(" ".join(args), SPHERE); save_sphere(SPHERE)
        except urllib.error.URLError as exc:
            print(f"(Mund nicht erreichbar: {exc}. Läuft Ollama auf {OLLAMA_HOST}?)"); return
        s = out["state"]
        print(f"[{s['mode']} · Essenz {s['essence']} · {s['from']} → {s['to']}"
              + (f" · Charakter {tuple(s['character'])}" if s.get("character") else "")
              + (f" · Selbstbild {tuple(s['self_essence'])}" if s.get("self_essence") else "") + "]")
        if out["crisis"]: print("⚠️  KRISE erkannt → an Mensch/Fachstelle weiterleiten!")
        if out.get("research"):
            e = out["research"]["essence"]
            print(f"🔭 Sinneseindruck: balance {e['balance']} · relevance {e['relevance']} · depth {e['depth']:+d}")
        print(out["reply"] or "(leer — Mund blieb stumm)")

if __name__ == "__main__":
    main()
