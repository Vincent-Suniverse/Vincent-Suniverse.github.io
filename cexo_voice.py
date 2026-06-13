"""
CEXO VOICE — die Sprachbrücke (cexo_voice.py)
==============================================
Der Kern denkt, der Mund spricht.

Eine eigenständige Schicht NEBEN dem heiligen Kern — wie cexo_research.py.
cexo_core.py importiert dies NICHT und bleibt blind und deterministisch.

Zwei Brücken:
    WAHRNEHMUNG  perceive(text) -> input_signal
        Ein DETERMINISTISCHER Parser (kein LLM) übersetzt Sprache in die
        vier Achsen {operation, reaction, intuition, depth}. Robust und
        testbar. Das Lexikon ist die anpassbare Kammer — hier justiert
        Vincent, wenn die Wahrnehmung sich falsch anfühlt.

    MUND  Mouth.speak(state) -> Text
        Der 1.5B (über Ollama) kleidet den Zustand des Kerns in Sprache.
        Tonfall nach Atem-Modus: HEAL sanft, EVOLVE treibend, OBSERVE klar.
        Er erfindet nichts — er spricht aus, was der Kern entschieden hat.
        Ohne Modell/Netz: ein deterministischer Stub, damit alles testbar
        bleibt (blind für den Mund, sehend für den Kern).

NUR Standardbibliothek. Keine externen Abhängigkeiten.

Sicherheits-Hinweis (Mental-Health-Kontext):
    perceive() liefert zusätzlich ein crisis-Flag. Die Anwendungs-Schicht
    MUSS markierte Eingaben an Menschen/Fachstellen weiterleiten — ein
    1.5B-Mund darf eine Krise niemals allein tragen. Der Wille zu heilen
    heißt auch: wissen, wann man nicht allein heilen kann.

Autor des Prinzips: Vincent (Chaos ex Ordo)
Bau: gemeinsam, Session 13.06.2026
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Optional

from cexo_core import AXES, MODE_NAMES, VALUE_MEANING


# ─────────────────────────────────────────────────────────────────────
#  WAHRNEHMUNG — deterministischer Parser: Text → input_signal
#  Das Lexikon ist die anpassbare Kammer. Erweiterbar, isoliert.
#  Konvention: +1 drängt zu Expansion(6), -1 zu Kontraktion(3), 0 Balance(9).
#  Der Betrag ist die Intensität (Achsen-Gewicht im Kern).
# ─────────────────────────────────────────────────────────────────────

_LEXICON: dict[str, dict[int, list[str]]] = {
    # depth = der Atem: -1 HEAL (Einkehr), +1 EVOLVE (Wachstum), 0 OBSERVE
    "depth": {
        -1: ["müde", "erschöpft", "kaputt", "ruhe", "ausruhen", "schlafen",
             "pause", "heilen", "wund", "verletzt", "schmerz", "leer",
             "überfordert", "zu viel", "rückzug", "innehalten"],
        +1: ["wachsen", "lernen", "mehr", "neu", "neues", "anfangen",
             "schaffen", "ziel", "weiter", "entwickeln", "aufbauen",
             "idee", "erschaffen", "vorwärts", "motiviert", "kraft"],
    },
    # reaction = emotionale Ladung: -1 nach innen (Trauer/Angst), +1 nach außen
    "reaction": {
        -1: ["traurig", "angst", "fürchte", "schlecht", "beschissen",
             "deprimiert", "hoffnungslos", "verzweifelt", "weinen",
             "einsam", "allein", "scham", "schuld"],
        +1: ["wütend", "sauer", "wut", "hass", "aufgeregt", "begeistert",
             "freu", "glücklich", "stark", "lebendig"],
    },
    # operation = Handlungskraft: +1 handeln, -1 nicht-können/Rückzug
    "operation": {
        +1: ["machen", "tun", "los", "arbeiten", "handeln", "bewegen",
             "starten", "bauen", "anpacken"],
        -1: ["kann nicht", "schaffe nicht", "blockiert", "festgefahren",
             "feststecke", "aufgeben", "geht nicht", "lähmt"],
    },
    # intuition = Sinn/Klarheit: +1 suchen/verstehen, -1 Verwirrung/Verlust
    "intuition": {
        +1: ["warum", "verstehen", "sinn", "bedeutung", "frage", "ahne",
             "begreifen", "klarheit"],
        -1: ["verwirrt", "weiß nicht", "keine ahnung", "verloren",
             "durcheinander", "chaos", "sinnlos", "orientierungslos"],
    },
}

# Krisen-Hinweise — die Anwendung MUSS solche Eingaben an Menschen leiten.
_CRISIS_CUES: list[str] = [
    "suizid", "selbstmord", "umbringen", "nicht mehr leben",
    "mich töten", "töte mich", "ritzen", "selbstverletzung",
    "kein ausweg", "will sterben", "beenden", "nicht mehr weiterleben",
]


def _count(cue: str, text: str) -> int:
    """Zählt Vorkommen eines Hinweises (Wortgrenzen, auch Mehrwort)."""
    return len(re.findall(r"\b" + re.escape(cue) + r"\b", text))


def detect_crisis(text: str) -> bool:
    """True, wenn die Eingabe auf eine akute Krise hindeutet."""
    t = (text or "").lower()
    return any(_count(cue, t) for cue in _CRISIS_CUES)


def perceive(text: str) -> dict:
    """
    Übersetzt Text deterministisch in ein input_signal für engine.step().
    Liefert zusätzlich '_crisis': bool (von der Anwendung zu behandeln).
    """
    t = (text or "").lower()
    signal: dict = {ax: 0 for ax in AXES}
    for axis, polarities in _LEXICON.items():
        for sign, cues in polarities.items():
            for cue in cues:
                signal[axis] += sign * _count(cue, t)
    signal["_crisis"] = detect_crisis(t)
    return signal


# ─────────────────────────────────────────────────────────────────────
#  MUND — der 1.5B (über Ollama) spricht den Zustand des Kerns
#  Tonfall nach Atem-Modus. Ohne Modell/Netz: deterministischer Stub.
# ─────────────────────────────────────────────────────────────────────

_MODE_TONE = {
    "HEAL": "sanft, bergend, verlangsamend — gib Sicherheit und Ruhe, "
            "dränge zu nichts.",
    "EVOLVE": "ermutigend, vorwärtsgewandt, kraftvoll — benenne den "
              "nächsten möglichen Schritt.",
    "OBSERVE": "ruhig, klar, gewahr — spiegele, ohne zu drängen.",
}

_STUB_OPENER = {
    "HEAL": "Ich bleibe bei dir. Lass uns kurz innehalten.",
    "EVOLVE": "Da ist Bewegung in dir. Lass uns ihr folgen.",
    "OBSERVE": "Ich bin da und nehme wahr, was ist.",
}


class Mouth:
    """
    Die Stimme. Spricht per Ollama, fällt ohne Modell/Netz auf einen
    deterministischen Stub zurück — damit die Brücke immer testbar ist.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        timeout: float = 30.0,
        offline: bool = False,
    ):
        self.model = model or os.environ.get("CEXO_OLLAMA_MODEL", "cexo-mund")
        self.host = (host or os.environ.get("CEXO_OLLAMA_HOST")
                     or "http://localhost:11434").rstrip("/")
        self.timeout = timeout
        self.offline = offline

    # ---- Prompt-Bau aus dem Kern-Zustand ----
    @staticmethod
    def _system_prompt(mode: str) -> str:
        tone = _MODE_TONE.get(mode, _MODE_TONE["OBSERVE"])
        return (
            "Du bist die Stimme von CEXO. Der deterministische Kern hat "
            "bereits entschieden, wohin die Bewegung geht. Du erfindest "
            "nichts und gibst keine klinischen Ratschläge — du sprichst nur "
            "aus, was der Zustand bedeutet, in höchstens zwei warmen Sätzen. "
            f"Tonfall ({mode}): {tone}"
        )

    @staticmethod
    def _user_prompt(state: dict) -> str:
        meaning = " | ".join(state.get("meaning", []))
        return (
            f"Modus: {state.get('mode')}  "
            f"Essenz: {state.get('essence')}  "
            f"Bewegung: {state.get('from')} → {state.get('to')}\n"
            f"Bedeutung der Achsen: {meaning}\n"
            "Sprich jetzt."
        )

    # ---- deterministischer Stub (kein Modell nötig) ----
    @staticmethod
    def _stub_text(state: dict) -> str:
        mode = state.get("mode", "OBSERVE")
        opener = _STUB_OPENER.get(mode, _STUB_OPENER["OBSERVE"])
        essence = state.get("essence")
        return f"{opener} (Essenz {essence}, Modus {mode})"

    # ---- Ollama-Aufruf ----
    def _ask_ollama(self, system: str, prompt: str) -> str:
        payload = json.dumps({
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("response") or "").strip()

    # ---- sprechen ----
    def speak(self, state: dict) -> dict:
        """
        Verwandelt einen Kern-Zustand in Sprache.
            source = "llm"  → vom 1.5B gesprochen
            source = "stub" → deterministischer Rückfall (offline/Fehler)
        """
        mode = state.get("mode", "OBSERVE")
        if self.offline:
            return {"text": self._stub_text(state), "source": "stub", "mode": mode}
        try:
            text = self._ask_ollama(self._system_prompt(mode), self._user_prompt(state))
            if not text:
                raise ValueError("leere Antwort")
            return {"text": text, "source": "llm", "mode": mode}
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, ValueError, OSError) as exc:
            stub = self._stub_text(state)
            return {"text": stub, "source": "stub", "mode": mode, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────
#  BEGEGNUNG — die ganze Brücke: perceive → engine.step → speak
# ─────────────────────────────────────────────────────────────────────

def converse(engine, text: str, mouth: Optional[Mouth] = None) -> dict:
    """
    Eine vollständige Begegnung. engine ist eine CexoEngine-Instanz.
    Reicht das crisis-Flag durch — die Anwendung MUSS darauf reagieren.
    """
    mouth = mouth or Mouth()
    signal = perceive(text)
    crisis = signal.pop("_crisis", False)
    state = engine.step(signal)
    spoken = mouth.speak(state)
    return {
        "input": text,
        "signal": signal,
        "crisis": crisis,
        "state": state,
        "voice": spoken,
    }


# ─────────────────────────────────────────────────────────────────────
#  OFFLINE-VERIFIKATION — deterministisch, ohne Modell, ohne Netz
# ─────────────────────────────────────────────────────────────────────

def verify_offline() -> dict:
    """Netzfreier Selbsttest der Wahrnehmung und des Stub-Mundes."""
    # 1) Wahrnehmung: Richtung der Achsen
    s_tired = perceive("ich bin so müde und erschöpft, alles zu viel")
    assert s_tired["depth"] < 0, "Erschöpfung muss Richtung HEAL zeigen"

    s_grow = perceive("ich will wachsen und etwas neues erschaffen")
    assert s_grow["depth"] > 0, "Wachstum muss Richtung EVOLVE zeigen"

    s_neutral = perceive("hallo")
    assert all(s_neutral[ax] == 0 for ax in AXES), "Neutral muss Null sein"

    # 2) Determinismus: gleiche Eingabe → gleiches Signal
    assert perceive("ich bin traurig") == perceive("ich bin traurig")

    # 3) Krisen-Flag
    assert perceive("ich will nicht mehr leben")["_crisis"] is True
    assert perceive("schöner tag heute")["_crisis"] is False

    # 4) Stub-Mund spricht deterministisch, ohne Modell
    mouth = Mouth(offline=True)
    fake_state = {"mode": "HEAL", "essence": (3, 3, 9),
                  "from": (9, 9, 9, 9), "to": (3, 9, 9, 3),
                  "meaning": [VALUE_MEANING[v] for v in (3, 9, 9, 3)]}
    spoken = mouth.speak(fake_state)
    assert spoken["source"] == "stub" and spoken["text"]
    assert mouth.speak(fake_state)["text"] == spoken["text"], "Stub muss stabil sein"

    return {"perception": True, "determinism": True, "crisis": True,
            "stub_voice": True, "intact": True}


# ─────────────────────────────────────────────────────────────────────
#  Selbsttest — offline garantiert, live nur falls Ollama läuft
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("CEXO-Stimme — Selbsttest\n" + "=" * 50)

    rep = verify_offline()
    print(f"Offline-Verifikation : {rep}")

    import cexo_core
    print(f"Kern importiert Voice? "
          f"{'cexo_voice' in cexo_core.__dict__}  (muss False sein)")

    print("\n— Wahrnehmung (deterministischer Parser) —")
    proben = [
        "Ich bin völlig erschöpft und will nur noch meine Ruhe.",
        "Ich will endlich wachsen und etwas Neues aufbauen!",
        "Ich weiß nicht mehr weiter, alles ist durcheinander.",
    ]
    for p in proben:
        sig = perceive(p)
        crisis = sig.pop("_crisis")
        print(f"   '{p[:42]}…'\n     → {sig}  crisis={crisis}")

    print("\n— Begegnung: perceive → step → speak (Stub, ohne Modell) —")
    engine = cexo_core.CexoEngine(state_path="sphere_state.json")
    mouth = Mouth(offline=True)   # erzwingt den deterministischen Stub
    for p in ["Mir geht es heute richtig schlecht.",
              "Ich habe eine Idee und will loslegen."]:
        result = converse(engine, p, mouth=mouth)
        v = result["voice"]
        print(f"   Du : {p}")
        print(f"   CEXO ({v['mode']}, {v['source']}): {v['text']}")
        if result["crisis"]:
            print("   ⚠️  Krise erkannt → an Mensch/Fachstelle weiterleiten!")

    print("\n— Live-Probe (nur falls Ollama läuft) —")
    live = Mouth()  # zeigt auf http://localhost:11434, Modell 'cexo-mund'
    state = engine.step(perceive("ich fühle mich ein wenig verloren"))
    out = live.speak({k: v for k, v in state.items()})
    if out["source"] == "llm":
        print(f"   1.5B spricht: {out['text']}")
    else:
        print(f"   Ollama nicht erreichbar ({out.get('error')}) → Stub: {out['text']}")
        print("   → Brücke bleibt funktionsfähig, sobald 'ollama create' läuft.")

    print("\nSprachbrücke bereit. Der Kern denkt, der Mund spricht.")
