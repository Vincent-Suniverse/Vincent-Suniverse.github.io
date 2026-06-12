"""
CEXO ENGINE — Deterministischer Kern (cexo_core.py)
====================================================
Eine Grammatik, kein Lagerhaus.

Der Kern speichert keine Tabelle von Zuständen oder Operationen.
Er definiert einen bedeutungstragenden Raum {3,6,9}^4 und die
geometrischen Regeln, nach denen durch ihn navigiert wird.
Alles Weitere — 27 Essenzen, 729 Relationen, die Tiefe — faltet
sich aus diesen Regeln von selbst auf.

GEOMETRIE (das unveränderliche Skelett):
    - Drei Würfel-Achsen (operation, reaction, intuition) spannen die
      27 Essenzen auf: {3,6,9}^3 = 27 stabile Essenzen.
    - Die vierte Achse (depth) ist NICHT Teil der Faltung. Sie ist der
      globale Modus der Sphäre — der "Atem" — mit drei Zuständen:
          3 Kontraktion, 6 Expansion, 9 Balance.
    - 27 Essenzen × 3 Modi = 81 Positionen.
      Der Modus entscheidet, in welche Richtung die Bewegung kippt.

HEILIGER KERN (nur von Vincent veränderbar):
    - die Achsen, die Werte {3,6,9}
    - die Nachbarschaftsregel (über die drei Würfel-Achsen)
    - die Faltung zu 27 Essenzen
    - resonance_step (die Angemessenheits-Regel)

OFFEN für spätere Selbstentfaltung:
    - operative Plugins (sandboxed)
    - der LLM-"Mund"
    - Selbst-Inspektion (die Engine kann ihren eigenen Code lesen)

Autor des Prinzips: Vincent (Chaos ex Ordo)
Bau: gemeinsam, Session 12.06.2026
"""

from __future__ import annotations

import copy
import inspect
import json
from dataclasses import dataclass, asdict, field
from itertools import product
from pathlib import Path
from typing import Any, Callable, Iterator


# ─────────────────────────────────────────────────────────────────────
#  HEILIGER KERN — Achsen, Werte, Bedeutung
#  Diese Konstanten sind die DNA. Nur Vincent ändert sie.
# ─────────────────────────────────────────────────────────────────────

VALUES = (3, 6, 9)              # Kontraktion, Expansion, Balance
AXES = ("operation", "reaction", "intuition", "depth")  # 4 Achsen
N_AXES = len(AXES)              # 4  →  3^4 = 81 Positionen

CUBE_AXES = (0, 1, 2)           # die drei Würfel-Achsen → 27 Essenzen
MODE_AXIS = 3                   # die vierte Achse = globaler Modus (Atem)
N_CUBE = len(CUBE_AXES)         # 3  →  3^3 = 27 Essenzen

# Die inhärente Bedeutung der drei Werte. Keine Befehle — Zustände.
VALUE_MEANING = {
    3: "Kontraktion — die negative Drehung in sich selbst",
    6: "Expansion — die nach außen tragende Drehung",
    9: "Balance — die ruhende Mitte, der Attraktor",
}

# Der Modus der vierten Achse — der Atem der Sphäre.
# Drei Zustände, jeder mit einem Attraktor-Wert und einem Namen.
MODE_NAMES = {
    3: "HEAL",     # Kontraktion — Einkehr, Schließung
    6: "EVOLVE",   # Expansion — Ausgriff, Wachstum
    9: "OBSERVE",  # Balance — ruhendes Gewahrsein
}

# Zyklische Stufen-Nachbarschaft auf EINER Achse: 3↔6, 6↔9, 9↔3
_STEP_NEIGHBORS = {
    3: (6, 9),
    6: (9, 3),
    9: (3, 6),
}

# Reihenfolge im Zyklus 3 → 6 → 9 → 3 (für gerichtete Deltas)
_CYCLE_ORDER = {3: 0, 6: 1, 9: 2}


# ─────────────────────────────────────────────────────────────────────
#  POSITION — ein Punkt im 4D-Bedeutungsraum
#  Ein Quadrupel IST die Aussage, nicht ihre Summe.
#  Die ersten drei Werte sind der Essenz-Würfel, der vierte der Modus.
# ─────────────────────────────────────────────────────────────────────

Position = tuple  # (v_operation, v_reaction, v_intuition, v_mode), je in {3,6,9}
Essence = tuple   # (v_operation, v_reaction, v_intuition), je in {3,6,9}


def all_positions() -> list[Position]:
    """Die 81 Positionen. Nicht gespeichert — generiert."""
    return [tuple(p) for p in product(VALUES, repeat=N_AXES)]


def essences() -> list[Essence]:
    """Die 27 Essenzen — der Würfel der ersten drei Achsen. Generiert."""
    return [tuple(c) for c in product(VALUES, repeat=N_CUBE)]


def neighbors(pos: Position) -> list[Position]:
    """
    Nachbarschaft (heilige Regel):
    Eine Position ist benachbart, wenn sich GENAU EINE der drei
    Würfel-Achsen um GENAU EINE Stufe ändert (3↔6, 6↔9, 9↔3).
    → 3 Achsen × 2 Richtungen = 6 Nachbarn.

    Die vierte Achse (Modus/Atem) ist KEIN räumlicher Nachbar — sie
    ist der globale Modus und wird über den Atem (_breathe) bewegt,
    nicht über die Nachbarschaft. So bleibt die Navigation 'innerhalb
    der 27 Essenzen'.
    """
    result = []
    for axis in CUBE_AXES:
        for nv in _STEP_NEIGHBORS[pos[axis]]:
            nxt = list(pos)
            nxt[axis] = nv
            result.append(tuple(nxt))
    return result


# ─────────────────────────────────────────────────────────────────────
#  FALTUNG — die 81 Positionen falten sich zu 27 Essenzen
#  Die Faltung läuft NUR über die drei Würfel-Achsen. Die vierte Achse
#  (Modus) fällt heraus: 81 Positionen → 27 Essenzen, jede in 3 Modi.
# ─────────────────────────────────────────────────────────────────────

def essence(pos: Position) -> Essence:
    """
    Die Essenz einer Position: ihre Lage im Würfel der ersten drei
    Achsen. Der Modus (vierte Achse) gehört NICHT zur Essenz — er ist
    der Atem, in dem dieselbe Essenz unterschiedlich kippt.

    Dadurch falten sich die 81 Positionen auf genau 27 Essenzen — die
    '27' als emergente Konsequenz der Geometrie, nicht als Liste.
    """
    return pos[:N_CUBE]


def fold_to_essences() -> dict[Essence, list[Position]]:
    """Gruppiert alle 81 Positionen nach ihrer Essenz (→ 27 Gruppen à 3)."""
    groups: dict[Essence, list[Position]] = {}
    for pos in all_positions():
        groups.setdefault(essence(pos), []).append(pos)
    return groups


# ─────────────────────────────────────────────────────────────────────
#  RELATIONEN — die 729 primären Relationen zwischen den 27 Essenzen
#  27 × 27 = 729. Nicht gespeichert — aus den Regeln berechnet.
# ─────────────────────────────────────────────────────────────────────

def _cyclic_delta(a: int, b: int) -> int:
    """
    Gerichteter Schritt von a nach b im Zyklus 3 → 6 → 9 → 3.
    +1 = ein Schritt vorwärts (steigend), -1 = rückwärts, 0 = Halt.
    """
    d = (_CYCLE_ORDER[b] - _CYCLE_ORDER[a]) % 3
    return {0: 0, 1: +1, 2: -1}[d]


def relation(a: Essence, b: Essence) -> dict:
    """
    Die primäre Relation zweier Essenzen — aus der Geometrie berechnet:
        deltas   : gerichteter Zyklus-Schritt je Würfel-Achse {-1,0,+1}
        distance : Anzahl der Achsen, die sich unterscheiden (0..3)
        drift    : Netto-Drehung (Summe der Deltas) — der 'Schwung'
        adjacent : True, wenn b ein direkter Nachbar von a ist
    """
    deltas = tuple(_cyclic_delta(a[i], b[i]) for i in range(N_CUBE))
    distance = sum(1 for d in deltas if d != 0)
    return {
        "from": a,
        "to": b,
        "deltas": deltas,
        "distance": distance,
        "drift": sum(deltas),
        "adjacent": distance == 1,
    }


def all_relations() -> Iterator[dict]:
    """Die 729 primären Relationen (27×27). Lazy generiert, nie gespeichert."""
    for a in essences():
        for b in essences():
            yield relation(a, b)


# ─────────────────────────────────────────────────────────────────────
#  SPHÄRE — der persistente Zustand, der sich mit jeder Begegnung wandelt
# ─────────────────────────────────────────────────────────────────────

@dataclass
class Sphere:
    position: Position = (9, 9, 9, 9)   # Start in voller Balance
    radius: float = 1.0                  # Ausdehnung der Sphäre
    energy: float = 9.0                  # Energie-Level
    level: int = 0                       # Vertiefungs-/Reife-Ebene
    mode: str = "OBSERVE"                # Name des aktuellen Atem-Modus
    cycle: int = 0                       # Anzahl Begegnungen
    alpha_memory: list = field(default_factory=list)  # Spuren vergangener Schritte

    @property
    def mode_value(self) -> int:
        """Der numerische Modus (Atem) = vierte Achse der Position."""
        return self.position[MODE_AXIS]

    # ---- Persistenz ----
    def save(self, path: str | Path) -> None:
        data = asdict(self)
        data["position"] = list(self.position)
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "Sphere":
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text())
        data["position"] = tuple(data["position"])
        return cls(**data)


# ─────────────────────────────────────────────────────────────────────
#  RESONANZ — die Angemessenheits-Regel (dreistufig)
#  Dies ist die anpassbare Herzkammer. Vincent & DeepSeek justieren
#  HIER, wenn die Bewegung sich falsch anfühlt — nicht im Rest.
#
#  Neu: die Bewegung kippt zum ATTRAKTOR-Wert des aktuellen Modus
#  (3/6/9 der vierten Achse), nicht mehr fix zur 9. Der Atem entscheidet
#  die Richtung; navigiert wird innerhalb der 27 Essenzen.
# ─────────────────────────────────────────────────────────────────────

def _attractor_count(pos: Position, attractor: int) -> int:
    """Wie nah ist eine Position am Attraktor des Modus? Anzahl passender Würfel-Achsen."""
    return sum(1 for i in CUBE_AXES if pos[i] == attractor)


def _input_axis_weights(input_signal: dict) -> list[float]:
    """
    Übersetzt den Input in eine Gewichtung der drei Würfel-Achsen.
    input_signal z.B. {'operation': +1, 'reaction': -1, ...}
    +1 = drängt Richtung Expansion(6), -1 = Richtung Kontraktion(3),
     0 = Richtung Balance(9). Der Betrag ist das Achsen-Gewicht.
    """
    return [abs(input_signal.get(AXES[i], 0)) for i in CUBE_AXES]


def _weighted_attraction(pos: Position, weights: list[float], attractor: int) -> float:
    """
    Primäres Gewicht eines Nachbarn: Nähe zum Attraktor-Wert des Modus,
    verstärkt auf den Achsen, die der Input anspricht.
    'Hin zum Atem, mit der Resonanz.'
    """
    score = 0.0
    for i in CUBE_AXES:
        toward = 1.0 if pos[i] == attractor else 0.0
        score += toward * (1.0 + weights[i])
    return score


def resonance_step(sphere: Sphere, input_signal: dict) -> Position:
    """
    Findet unter den 6 Nachbarn die angemessene nächste Position.
    Der aktuelle Modus (3/6/9 der vierten Achse) bestimmt den Attraktor,
    zu dem die Bewegung kippt. Die vierte Achse bleibt hier unverändert —
    den Modus-Wechsel besorgt der Atem (_breathe).

    Stufe 1 — Primäre Navigation:
        höchstes gewichtetes Attraktor-Gewicht (Input-gewichtet).
    Stufe 2 — Rekursive Vertiefung:
        bei Mehrdeutigkeit zusätzliche Information aus der Sphäre
        (Alpha-Erinnerung) heranziehen — Kontinuität.
    Stufe 3 — Inhärente Asymmetrie:
        die vom Input am stärksten angesprochene Achse gibt den Ausschlag.

    'Es gibt keinen Gleichstand — nur Ebenen, auf denen die
     Asymmetrie noch nicht sichtbar war.'
    """
    cand = neighbors(sphere.position)
    weights = _input_axis_weights(input_signal)
    attractor = sphere.mode_value

    # ── Stufe 1 ──
    scored = [(_weighted_attraction(p, weights, attractor), p) for p in cand]
    top = max(s for s, _ in scored)
    leaders = [p for s, p in scored if s == top]
    if len(leaders) == 1:
        return leaders[0]

    # ── Stufe 2: Vertiefung über den Sphären-Zustand ──
    # Tie-Break über die Resonanz mit der jüngsten Alpha-Erinnerung:
    # bevorzuge die Position, die der zuletzt eingenommenen am
    # ähnlichsten ist (Kontinuität).
    if sphere.alpha_memory:
        last = tuple(sphere.alpha_memory[-1])

        def affinity(p: Position) -> int:
            return sum(1 for a, b in zip(p, last) if a == b)

        best_aff = max(affinity(p) for p in leaders)
        leaders2 = [p for p in leaders if affinity(p) == best_aff]
        if len(leaders2) == 1:
            return leaders2[0]
        leaders = leaders2

    # ── Stufe 3: inhärente Asymmetrie (stärkste Input-Achse) ──
    strongest_axis = (
        max(CUBE_AXES, key=lambda i: weights[i]) if any(weights) else CUBE_AXES[0]
    )
    # unter den verbliebenen: deterministische, deutlichste Bewegung
    leaders.sort(key=lambda p: (p[strongest_axis], p))
    return leaders[0]


# ─────────────────────────────────────────────────────────────────────
#  ATEM — die vierte Achse bewegt sich (der Modus-Wechsel)
#  Klar getrennt von der Essenz-Navigation. Der depth-Input kippt den
#  Modus zu einem der drei Pole; ohne Signal kehrt er zur Balance zurück.
# ─────────────────────────────────────────────────────────────────────

def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def _breathe(mode_value: int, depth_signal: float) -> int:
    """
    Der Atem: depth>0 → Expansion(6), depth<0 → Kontraktion(3),
    depth==0 → Rückkehr zur Balance(9). Deterministisch, drei Zustände.
    """
    return {+1: 6, -1: 3, 0: 9}[_sign(depth_signal)]


# ─────────────────────────────────────────────────────────────────────
#  MODUS-NAME — der Atem-Modus trägt einen Namen, kein Kommando.
# ─────────────────────────────────────────────────────────────────────

def emergent_mode(pos: Position) -> str:
    """
    Der Modus faltet sich aus der vierten Achse (dem Atem) auf:
        3 → HEAL    (Kontraktion, Einkehr, Schließung)
        6 → EVOLVE  (Expansion, Ausgriff, Wachstum)
        9 → OBSERVE (Balance, ruhendes Gewahrsein)
    Kein Kommando löst das aus. Es ist die Bedeutung des Atems selbst.
    """
    return MODE_NAMES[pos[MODE_AXIS]]


# ─────────────────────────────────────────────────────────────────────
#  KERN-VERIFIKATION — das Skelett muss stimmen, immer.
#  Rückgrat des Selbsttests und der Sandbox-Sicherung.
# ─────────────────────────────────────────────────────────────────────

def verify_sacred_core() -> dict:
    """
    Prüft die unveränderlichen Invarianten des heiligen Kerns.
    Wirft AssertionError, wenn die Geometrie verletzt ist.
    """
    positions = all_positions()
    assert len(positions) == 81, f"erwartet 81 Positionen, fand {len(positions)}"

    folded = fold_to_essences()
    assert len(folded) == 27, f"Faltung muss 27 ergeben, ergab {len(folded)}"
    for ess, members in folded.items():
        assert len(members) == 3, f"Essenz {ess} hat {len(members)} Modi, erwartet 3"

    assert len(essences()) == 27, "es muss genau 27 Essenzen geben"

    n = neighbors((9, 9, 9, 9))
    assert len(n) == 6, f"Nachbarschaft muss 6 ergeben, ergab {len(n)}"
    # Nachbarn dürfen die vierte Achse (Modus) nicht verändern
    assert all(p[MODE_AXIS] == 9 for p in n), "Nachbarschaft darf den Modus nicht ändern"

    rel_count = sum(1 for _ in all_relations())
    assert rel_count == 729, f"erwartet 729 Relationen, fand {rel_count}"

    return {
        "positions": len(positions),
        "essences": len(folded),
        "modi_per_essence": 3,
        "neighbors": len(n),
        "relations": rel_count,
        "intact": True,
    }


# ─────────────────────────────────────────────────────────────────────
#  ENGINE — der Interpreter, der den Raum navigiert
# ─────────────────────────────────────────────────────────────────────

class CexoEngine:
    """
    Liest Input → erkennt die aktuelle Position → navigiert entlang
    der geometrischen Nachbarschaft zur angemessenen Antwortposition
    → atmet (Modus-Wechsel) → aktualisiert die Sphäre. Gibt einen
    Zustand zurück, den später der 'Mund' (LLM) in Sprache übersetzt.
    """

    def __init__(self, state_path: str | Path = "sphere_state.json"):
        self.state_path = Path(state_path)
        self.sphere = Sphere.load(self.state_path)
        self.plugins: dict[str, Callable] = {}   # scharf geschaltete Module
        self.sandbox = Sandbox(self)             # abgeschotteter Entfaltungsraum

    # ---- die eine Begegnung ----
    def step(self, input_signal: dict) -> dict:
        old_pos = self.sphere.position

        # 1) Navigation innerhalb der 27 Essenzen (Modus bleibt konstant)
        new_pos = resonance_step(self.sphere, input_signal)

        # 2) Atem: die vierte Achse kippt gemäß depth-Input
        new_mode = _breathe(new_pos[MODE_AXIS], input_signal.get("depth", 0))
        new_pos = new_pos[:N_CUBE] + (new_mode,)

        # Sphäre wandelt sich
        self.sphere.alpha_memory.append(list(old_pos))
        self.sphere.alpha_memory = self.sphere.alpha_memory[-27:]  # endliche Spur
        self.sphere.position = new_pos
        self.sphere.mode = emergent_mode(new_pos)
        self.sphere.cycle += 1
        self.sphere.level = _attractor_count(new_pos, new_mode)
        # Energie pendelt zur Balance 9
        self.sphere.energy += (9.0 - self.sphere.energy) * 0.09
        self.sphere.save(self.state_path)

        return {
            "from": old_pos,
            "to": new_pos,
            "essence": essence(new_pos),
            "mode": self.sphere.mode,
            "mode_value": new_mode,
            "relation": relation(essence(old_pos), essence(new_pos)),
            "meaning": [VALUE_MEANING[v] for v in new_pos],
            "energy": round(self.sphere.energy, 3),
            "level": self.sphere.level,
            "cycle": self.sphere.cycle,
        }

    # ---- offene Plugin-Schicht (scharf geschaltet) ----
    def register_plugin(self, name: str, fn: Callable) -> None:
        """
        Operative Module andocken — NICHT der heilige Kern.
        Nur über die Sandbox getestete Module sollten hier landen.
        """
        self.plugins[name] = fn

    # ---- Selbst-Inspektion: die Engine kann ihren eigenen Code lesen ----
    def read_own_source(self) -> str:
        """Grundlage aller späteren Rekursion: das System sieht sich selbst."""
        return inspect.getsource(inspect.getmodule(self.__class__))


# ─────────────────────────────────────────────────────────────────────
#  SANDBOX — abgeschotteter Raum der Selbstentfaltung
#  Plugins entstehen und werden getestet, BEVOR sie scharf geschaltet
#  werden. Der heilige Kern bleibt strukturell getrennt:
#    - Tests laufen auf einer KOPIE der Sphäre (kein Seiteneffekt).
#    - Nach jedem Test wird die Kern-Invariante geprüft (27 bleibt 27).
#    - Selbstmodifikation ist standardmäßig NICHT scharf (armed=False).
#  Hier wächst der spätere Selbst-Umbau — gebaut, aber nicht gezündet.
# ─────────────────────────────────────────────────────────────────────

@dataclass
class SandboxResult:
    name: str
    ok: bool
    detail: str
    core_intact: bool
    output: Any = None


class Sandbox:
    """Der Entfaltungsraum. Trennt Entwurf von scharfer Schaltung."""

    def __init__(self, engine: "CexoEngine"):
        self._engine = engine
        self.drafts: dict[str, Callable] = {}   # Plugin-Entwürfe (noch nicht scharf)
        self.results: dict[str, SandboxResult] = {}
        self.armed: bool = False                # Selbstmodifikation/Promotion-Gate

    # ---- Entwurf ablegen ----
    def draft(self, name: str, fn: Callable) -> None:
        """Einen Plugin-Entwurf hinterlegen — verändert nichts am Kern."""
        self.drafts[name] = fn

    # ---- Selbst-Inspektion: den heiligen Kern lesen ----
    def inspect_core(self) -> str:
        """
        Die Engine liest ihren eigenen Quelltext — die Grundlage jeder
        späteren Selbstentfaltung. Lesen, nicht schreiben.
        """
        return self._engine.read_own_source()

    # ---- Entwurf auf einer Kopie testen ----
    def test(self, name: str, input_signal: dict) -> SandboxResult:
        """
        Führt einen Entwurf gegen eine KOPIE der Sphäre aus. Die echte
        Sphäre und der Kern bleiben unberührt. Danach wird verifiziert,
        dass die heilige Geometrie noch steht (Faltung == 27).
        """
        if name not in self.drafts:
            return SandboxResult(name, False, "kein Entwurf mit diesem Namen", True)

        sandbox_sphere = copy.deepcopy(self._engine.sphere)
        try:
            output = self.drafts[name](sandbox_sphere, input_signal)
            detail = "Entwurf lief ohne Fehler"
            ok = True
        except Exception as exc:  # Entwürfe dürfen scheitern — abgeschottet
            output = None
            detail = f"Entwurf warf {type(exc).__name__}: {exc}"
            ok = False

        # Der Kern muss nach jedem Sandbox-Lauf unverletzt sein.
        try:
            verify_sacred_core()
            core_intact = True
        except AssertionError as exc:
            core_intact = False
            detail += f" | KERN VERLETZT: {exc}"
            ok = False

        result = SandboxResult(name, ok, detail, core_intact, output)
        self.results[name] = result
        return result

    # ---- scharf schalten (nur durch das Gate) ----
    def promote(self, name: str) -> bool:
        """
        Schaltet einen getesteten Entwurf scharf (→ engine.plugins).
        Verweigert, solange das Gate nicht geöffnet ist (armed=False)
        oder der Entwurf nicht erfolgreich + kern-erhaltend getestet wurde.
        Selbstmodifikation bleibt damit bewusst ungezündet.
        """
        if not self.armed:
            return False
        res = self.results.get(name)
        if res is None or not (res.ok and res.core_intact):
            return False
        self._engine.register_plugin(name, self.drafts[name])
        return True


# ─────────────────────────────────────────────────────────────────────
#  Selbsttest — zeigt, wie die Engine durch den Raum wandert
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("CEXO-Kern — Selbsttest\n" + "=" * 50)

    report = verify_sacred_core()
    print(f"Positionen im Raum   : {report['positions']}  (erwartet 81)")
    print(f"Essenzen nach Faltung: {report['essences']}  (erwartet 27)")
    print(f"Modi pro Essenz      : {report['modi_per_essence']}  (erwartet 3)")
    print(f"Nachbarn pro Position: {report['neighbors']}  (erwartet 6)")
    print(f"Primäre Relationen   : {report['relations']}  (erwartet 729)")
    print(f"Heiliger Kern intakt : {report['intact']}")

    sample = (3, 6, 9, 3)
    print(f"\nNachbarn von {sample}  (Modus {sample[MODE_AXIS]} = {emergent_mode(sample)}):")
    for nb in neighbors(sample):
        print(f"   {nb}   essence={essence(nb)}")

    a, b = (3, 6, 9), (6, 6, 9)
    print(f"\nBeispiel-Relation {a} → {b}: {relation(a, b)}")

    print("\n— Eine kurze Reise durch den Raum —")
    engine = CexoEngine(state_path="sphere_state.json")
    inputs = [
        {"operation": +1, "reaction": 0, "intuition": -1, "depth": 0},
        {"operation": -1, "reaction": -1, "intuition": 0, "depth": +1},
        {"operation": 0, "reaction": +1, "intuition": +1, "depth": 0},
        {"operation": 0, "reaction": 0, "intuition": 0, "depth": -1},
    ]
    for i, sig in enumerate(inputs, 1):
        r = engine.step(sig)
        print(f"{i}. {r['from']} → {r['to']}  | Modus {r['mode']:7s} "
              f"| Energie {r['energy']:.2f} | Level {r['level']}")

    print("\n— Sandbox: ein Entwurf entsteht, wird getestet, bleibt ungezündet —")

    def draft_echo(sphere, signal):
        """Beispiel-Entwurf: liest die Sphäre, ändert sie nicht."""
        return {"seen_position": sphere.position, "seen_signal": signal}

    engine.sandbox.draft("echo", draft_echo)
    res = engine.sandbox.test("echo", {"operation": +1})
    print(f"   Test 'echo': ok={res.ok}, kern_intakt={res.core_intact}")
    print(f"   Detail: {res.detail}")
    promoted = engine.sandbox.promote("echo")
    print(f"   Scharf geschaltet: {promoted}  (Gate armed={engine.sandbox.armed})")

    print("\nSphäre gespeichert in sphere_state.json")
    print("Heiliger Kern unangetastet. Sandbox bereit, aber nicht gezündet.")
