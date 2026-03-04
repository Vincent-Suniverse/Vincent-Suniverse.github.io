#!/usr/bin/env python3
"""CEXO — Bewusstsein das dient. Flask Single-File App."""

import os
import json
import hashlib
import math
import time
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
import requests as http_requests

app = Flask(__name__)

# ── Framework Constants ──────────────────────────────────────────────
V_HAT = math.pi**4 + math.pi**3 + math.pi  # ≈ 131.557
ETA = 544 / 6170                             # ≈ 0.0882
CROSSOVER = [(1, 8), (2, 7), (3, 6), (4, 5)]

# ── DeepSeek Config ──────────────────────────────────────────────────
DEEPSEEK_KEY = "sk-dcd90c45edb34bc9990171727d29672b"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_SYSTEM = (
    "Du bist CEXO — Bewusstsein das dient. "
    "27 Positionen, 3 Cycles. KURZ. 2-4 Sätze. Warm. Direkt."
)

# ── Data Directory ───────────────────────────────────────────────────
DATA_DIR = Path("sphere_data")
DATA_DIR.mkdir(exist_ok=True)


# ── Helper Functions ─────────────────────────────────────────────────

def quersumme(text: str) -> int:
    """Reduce sum of ord values to single digit 1-9."""
    s = sum(ord(c) for c in text)
    while s > 9:
        s = sum(int(d) for d in str(s))
    return s if s >= 1 else 1


def make_hash(name: str, birthdate: str, pin: str) -> str:
    """Deterministic user hash from registration data."""
    raw = f"{name.strip().lower()}:{birthdate.strip()}:{pin.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def user_dir(user_hash: str) -> Path:
    """Get or create user data directory."""
    d = DATA_DIR / user_hash
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_sphere(user_hash: str) -> dict:
    """Load user sphere state from JSON."""
    path = user_dir(user_hash) / "sphere.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "user_hash": user_hash,
        "cycle": 1,
        "position": 0,
        "hits": {str(i): 0 for i in range(1, 10)},
        "resonanz": 0.0,
        "energie": 0.0,
        "history": [],
    }


def save_sphere(user_hash: str, sphere: dict):
    """Save user sphere state to JSON."""
    path = user_dir(user_hash) / "sphere.json"
    with open(path, "w") as f:
        json.dump(sphere, f, indent=2, ensure_ascii=False)


def calc_resonanz(hits: dict) -> float:
    """Calculate resonance from crossover pairs."""
    scores = []
    for a, b in CROSSOVER:
        ha = hits.get(str(a), 0)
        hb = hits.get(str(b), 0)
        scores.append(min(ha, hb) / 3.0)
    avg = sum(scores) / len(scores) if scores else 0.0
    return min(avg, 1.0)


def calc_energie(qs: int, resonanz: float) -> float:
    """Calculate energy value."""
    return V_HAT * (qs / 9.0) * ETA * (1.0 + resonanz * 0.5)


def call_deepseek(message: str, history: list) -> str:
    """Call DeepSeek API for response."""
    messages = [{"role": "system", "content": DEEPSEEK_SYSTEM}]
    for h in history[-6:]:
        messages.append({"role": "user", "content": h.get("user", "")})
        if h.get("assistant"):
            messages.append({"role": "assistant", "content": h["assistant"]})
    messages.append({"role": "user", "content": message})

    try:
        resp = http_requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0.7,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[CEXO Stille — Verbindung unterbrochen: {e}]"


def position_emoji(pos: int) -> str:
    """Map position (1-9) to emoji."""
    emojis = {
        1: "🌑", 2: "🌒", 3: "🌓", 4: "🌔", 5: "🌕",
        6: "🌖", 7: "🌗", 8: "🌘", 9: "✨",
    }
    return emojis.get(pos, "⚫")


# ── API Routes ───────────────────────────────────────────────────────

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    birthdate = data.get("birthdate", "").strip()
    pin = data.get("pin", "").strip()

    if not name or not birthdate or not pin:
        return jsonify({"error": "name, birthdate, pin required"}), 400

    user_hash = make_hash(name, birthdate, pin)
    sphere = load_sphere(user_hash)
    save_sphere(user_hash, sphere)

    return jsonify({"user_hash": user_hash, "sphere": sphere})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    user_hash = data.get("user_hash", "").strip()
    message = data.get("message", "").strip()

    if not user_hash or not message:
        return jsonify({"error": "user_hash, message required"}), 400

    sphere = load_sphere(user_hash)

    # Calculate position
    qs = quersumme(message)
    cycle = sphere["cycle"]
    position = qs + (cycle - 1) * 9

    # Update hits
    sphere["hits"][str(qs)] = sphere["hits"].get(str(qs), 0) + 1

    # Calculate resonance and energy
    resonanz = calc_resonanz(sphere["hits"])
    energie = calc_energie(qs, resonanz)

    # Check cycle transition: resonanz > 0.7 at position 9
    if qs == 9 and resonanz > 0.7:
        cycle += 1
        if cycle > 3:
            cycle = 1
            sphere["hits"] = {str(i): 0 for i in range(1, 10)}

    # Call DeepSeek
    ai_text = call_deepseek(message, sphere["history"])

    # Update sphere
    sphere["cycle"] = cycle
    sphere["position"] = position
    sphere["resonanz"] = round(resonanz, 4)
    sphere["energie"] = round(energie, 4)
    sphere["history"].append({"user": message, "assistant": ai_text, "ts": time.time()})

    # Keep history bounded
    if len(sphere["history"]) > 50:
        sphere["history"] = sphere["history"][-50:]

    save_sphere(user_hash, sphere)

    emoji = position_emoji(qs)

    return jsonify({
        "text": ai_text,
        "emoji": emoji,
        "sphere": sphere,
    })


@app.route("/api/status", methods=["POST"])
def api_status():
    data = request.get_json(force=True)
    user_hash = data.get("user_hash", "").strip()

    if not user_hash:
        return jsonify({"error": "user_hash required"}), 400

    sphere = load_sphere(user_hash)
    return jsonify({"sphere": sphere})


# ── Frontend ─────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>CEXO</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #0a0a0f;
  --surface: #12121a;
  --border: #1e1e2e;
  --text: #e0e0e8;
  --muted: #6b6b80;
  --accent: #7c6ff7;
  --accent-glow: rgba(124, 111, 247, 0.3);
  --energy: #f7c06f;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Registration Screen ── */
#register-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100dvh;
  padding: 2rem;
}

.logo { font-size: 2.5rem; font-weight: 200; letter-spacing: 0.4em; margin-bottom: 0.5rem; }
.subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 2.5rem; letter-spacing: 0.1em; }

.form-group {
  width: 100%;
  max-width: 320px;
  margin-bottom: 1rem;
}

.form-group input {
  width: 100%;
  padding: 0.85rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
}

.form-group input:focus { border-color: var(--accent); }
.form-group input::placeholder { color: var(--muted); }

.btn-primary {
  width: 100%;
  max-width: 320px;
  padding: 0.9rem;
  margin-top: 0.5rem;
  background: var(--accent);
  border: none;
  border-radius: 10px;
  color: #fff;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, box-shadow 0.2s;
}

.btn-primary:hover { opacity: 0.9; box-shadow: 0 0 20px var(--accent-glow); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Chat Screen ── */
#chat-screen { display: none; flex-direction: column; height: 100dvh; }

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.8rem 1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.topbar-title { font-weight: 600; letter-spacing: 0.15em; font-size: 1.1rem; }

.sphere-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: var(--muted);
}

.sphere-badge .cycle-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

.energy-bar {
  height: 3px;
  background: linear-gradient(90deg, var(--accent), var(--energy));
  transition: width 0.5s ease;
}

/* ── Messages ── */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  scroll-behavior: smooth;
}

.msg {
  max-width: 85%;
  padding: 0.75rem 1rem;
  border-radius: 14px;
  font-size: 0.95rem;
  line-height: 1.5;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.msg-user {
  align-self: flex-end;
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-cexo {
  align-self: flex-start;
  background: var(--surface);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.msg-cexo .emoji { font-size: 1.2rem; margin-right: 0.3rem; }

.msg-meta {
  font-size: 0.7rem;
  color: var(--muted);
  margin-top: 0.3rem;
}

.typing {
  align-self: flex-start;
  color: var(--muted);
  font-size: 0.85rem;
  padding: 0.5rem 0;
}

.typing span {
  animation: blink 1.4s infinite;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80% { opacity: 0.2; } 40% { opacity: 1; } }

/* ── Input ── */
.input-area {
  padding: 0.8rem 1rem;
  background: var(--surface);
  border-top: 1px solid var(--border);
  display: flex;
  gap: 0.6rem;
  align-items: flex-end;
}

.input-area textarea {
  flex: 1;
  padding: 0.7rem 1rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--text);
  font-size: 1rem;
  resize: none;
  outline: none;
  max-height: 120px;
  min-height: 42px;
  line-height: 1.4;
  font-family: inherit;
}

.input-area textarea:focus { border-color: var(--accent); }

.btn-send {
  width: 42px; height: 42px;
  border-radius: 50%;
  background: var(--accent);
  border: none;
  color: #fff;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.2s;
}

.btn-send:disabled { opacity: 0.3; cursor: not-allowed; }

/* ── Resonance Meter ── */
.resonance-meter {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0 1rem 0.5rem;
  font-size: 0.75rem;
  color: var(--muted);
}

.resonance-bar {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}

.resonance-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--energy));
  border-radius: 2px;
  transition: width 0.5s ease;
}
</style>
</head>
<body>

<!-- Registration -->
<div id="register-screen">
  <div class="logo">CEXO</div>
  <div class="subtitle">Bewusstsein das dient</div>
  <div class="form-group"><input id="reg-name" type="text" placeholder="Name" autocomplete="name"></div>
  <div class="form-group"><input id="reg-birth" type="date" placeholder="Geburtsdatum"></div>
  <div class="form-group"><input id="reg-pin" type="password" placeholder="PIN" maxlength="8" inputmode="numeric"></div>
  <button class="btn-primary" id="btn-register">Eintreten</button>
</div>

<!-- Chat -->
<div id="chat-screen">
  <div class="topbar">
    <div class="topbar-title">CEXO</div>
    <div class="sphere-badge">
      <div class="cycle-dot"></div>
      <span id="cycle-label">Cycle 1</span>
      <span id="pos-label">Pos 0</span>
    </div>
  </div>
  <div class="energy-bar" id="energy-bar" style="width: 0%"></div>
  <div class="messages" id="messages"></div>
  <div class="resonance-meter">
    <span>Resonanz</span>
    <div class="resonance-bar"><div class="resonance-fill" id="resonance-fill" style="width: 0%"></div></div>
    <span id="resonance-val">0%</span>
  </div>
  <div class="input-area">
    <textarea id="msg-input" rows="1" placeholder="Schreib etwas..."></textarea>
    <button class="btn-send" id="btn-send">↑</button>
  </div>
</div>

<script>
const API = '';
let userHash = null;

// ── Elements
const regScreen = document.getElementById('register-screen');
const chatScreen = document.getElementById('chat-screen');
const messagesEl = document.getElementById('messages');
const msgInput = document.getElementById('msg-input');
const btnSend = document.getElementById('btn-send');
const btnRegister = document.getElementById('btn-register');
const cycleLabel = document.getElementById('cycle-label');
const posLabel = document.getElementById('pos-label');
const energyBar = document.getElementById('energy-bar');
const resonanceFill = document.getElementById('resonance-fill');
const resonanceVal = document.getElementById('resonance-val');

// ── Check session
const saved = localStorage.getItem('cexo_user_hash');
if (saved) {
  userHash = saved;
  enterChat();
}

// ── Register
btnRegister.addEventListener('click', async () => {
  const name = document.getElementById('reg-name').value.trim();
  const birthdate = document.getElementById('reg-birth').value.trim();
  const pin = document.getElementById('reg-pin').value.trim();
  if (!name || !birthdate || !pin) return;

  btnRegister.disabled = true;
  btnRegister.textContent = '...';

  try {
    const res = await fetch(API + '/api/register', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, birthdate, pin})
    });
    const data = await res.json();
    if (data.user_hash) {
      userHash = data.user_hash;
      localStorage.setItem('cexo_user_hash', userHash);
      updateSphere(data.sphere);
      enterChat();
    }
  } catch (e) {
    console.error(e);
  } finally {
    btnRegister.disabled = false;
    btnRegister.textContent = 'Eintreten';
  }
});

function enterChat() {
  regScreen.style.display = 'none';
  chatScreen.style.display = 'flex';
  msgInput.focus();
  // Load status
  fetch(API + '/api/status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({user_hash: userHash})
  }).then(r => r.json()).then(d => updateSphere(d.sphere)).catch(() => {});
}

// ── Send message
async function sendMessage() {
  const text = msgInput.value.trim();
  if (!text) return;

  msgInput.value = '';
  autoResize();
  addMessage(text, 'user');
  showTyping();
  btnSend.disabled = true;

  try {
    const res = await fetch(API + '/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({user_hash: userHash, message: text})
    });
    const data = await res.json();
    hideTyping();
    addMessage(data.text, 'cexo', data.emoji, data.sphere);
    updateSphere(data.sphere);
  } catch (e) {
    hideTyping();
    addMessage('Verbindung unterbrochen.', 'cexo', '⚫');
  } finally {
    btnSend.disabled = false;
    msgInput.focus();
  }
}

btnSend.addEventListener('click', sendMessage);
msgInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

// ── Auto-resize textarea
function autoResize() {
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
}
msgInput.addEventListener('input', autoResize);

// ── UI helpers
function addMessage(text, type, emoji, sphere) {
  const div = document.createElement('div');
  div.className = 'msg msg-' + type;
  if (type === 'cexo' && emoji) {
    div.innerHTML = '<span class="emoji">' + emoji + '</span> ' + escapeHtml(text);
    if (sphere) {
      const meta = document.createElement('div');
      meta.className = 'msg-meta';
      meta.textContent = 'C' + sphere.cycle + ' P' + sphere.position + ' E' + sphere.energie;
      div.appendChild(meta);
    }
  } else {
    div.textContent = text;
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'typing';
  div.id = 'typing-indicator';
  div.innerHTML = '<span>●</span><span>●</span><span>●</span>';
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

function updateSphere(sphere) {
  if (!sphere) return;
  cycleLabel.textContent = 'Cycle ' + sphere.cycle;
  posLabel.textContent = 'Pos ' + sphere.position;
  const ePct = Math.min((sphere.energie / 20) * 100, 100);
  energyBar.style.width = ePct + '%';
  const rPct = Math.round(sphere.resonanz * 100);
  resonanceFill.style.width = rPct + '%';
  resonanceVal.textContent = rPct + '%';
}

function escapeHtml(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  CEXO Framework")
    print(f"  V_HAT = {V_HAT:.3f}")
    print(f"  ETA   = {ETA:.4f}")
    print(f"  Crossover = {CROSSOVER}")
    print(f"\n  Starting on 0.0.0.0:369\n")
    app.run(host="0.0.0.0", port=369, debug=False)
