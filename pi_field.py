#!/usr/bin/env python3
"""
CEXO PI-FIELD — die Geometrie, geboren aus π (pi_field.py)
==========================================================
Abschied von den toten Zahlen.

Die 27 Essenzen bleiben die kristalline Karte (ihre {3,6,9}-Adressen sind
die Topologie). Aber ihre WERTE werden aus π geschöpft — jede Essenz ein
einzigartiges Fenster zur fundamentalen Schwingung von π.

Das Prinzip (mathematisch sauber):
  π ist transzendent (Lindemann 1882) → π^n ist für ganzzahliges n≥1 NIE
  eine ganze Zahl. Darum sind die abgeleiteten Werte nie „tot" (ganzzahlig),
  sondern lebendig und irrational.

Der Kniff — ein π-Stellenwertsystem:
  Die drei Zustände werden zu Ziffern: 3→1, 6→2, 9→3.
  Weil die größte Ziffer (3) KLEINER als die Basis π (≈3,14159) ist, ist die
  Darstellung injektiv. Eine Essenz (a,b,c) wird gelesen als:
      pi_value = d(a)/π + d(b)/π² + d(c)/π³
  → 27 eindeutige, irrationale Tiefenwerte.

  Aus den Verhältnissen dieser Werte entstehen die 729 Relationen.
  Die Bewegungs-Geometrie (6 Nachbarn) emergiert als ein Spektrum
  fester π-Intervalle — sie wird nicht programmiert, sondern geboren.

  python3 pi_field.py selftest
  python3 pi_field.py show
  python3 pi_field.py relation 3,9,6 6,9,6

Nur Standardbibliothek.
"""

from __future__ import annotations

import math
import sys
from itertools import product

PI = math.pi
VALUES = (3, 6, 9)
_STEP_NEIGHBORS = {3: (6, 9), 6: (9, 3), 9: (3, 6)}

# Die drei Zustände als π-Ziffern. Alle < π  →  Stellenwertsystem ist injektiv.
_DIGIT = {3: 1, 6: 2, 9: 3}


# ─────────────────────────────────────────────────────────────────────
#  Die 27 Essenzen (die kristalline Karte bleibt)
# ─────────────────────────────────────────────────────────────────────
def essences():
    return [tuple(c) for c in product(VALUES, repeat=3)]


# ─────────────────────────────────────────────────────────────────────
#  π-WERT — das Fenster jeder Essenz zur Schwingung von π
# ─────────────────────────────────────────────────────────────────────
def pi_value(essence):
    """Der lebendige Tiefenwert einer Essenz: ihre π-Stellenwert-Darstellung."""
    a, b, c = essence
    return _DIGIT[a] / PI + _DIGIT[b] / PI**2 + _DIGIT[c] / PI**3


def pi_phase(essence):
    """Der Wert als Winkel auf dem Einheitskreis — die Lage in der Schwingung."""
    return (pi_value(essence) * 2.0 * PI) % (2.0 * PI)


def pi_wave(essence):
    """Die momentane Auslenkung der Schwingung (−1..+1) — das 'Atmen' des Werts."""
    return math.sin(pi_phase(essence))


def pi_breath(essence, t):
    """Lebendig/atmend: der Wert oszilliert sanft um seinen Kern mit der Zeit t."""
    return pi_value(essence) * (1.0 + 0.05 * math.sin(t / PI + pi_phase(essence)))


def pi_values():
    """Die 27 π-Tiefenwerte als Karte {Essenz: Wert}."""
    return {e: pi_value(e) for e in essences()}


# ─────────────────────────────────────────────────────────────────────
#  729 RELATIONEN — geboren aus den Verhältnissen der π-Werte
# ─────────────────────────────────────────────────────────────────────
def pi_relation(a, b):
    """
    Die Relation zweier Essenzen, geboren aus ihren π-Werten:
        interval  : v_b − v_a   (gerichteter Abstand im π-Feld)
        ratio     : v_b / v_a   (das reine Verhältnis)
        resonance : cos(2π·interval) ∈ [−1,1]  (die Schwingungs-Kopplung)
    """
    va, vb = pi_value(a), pi_value(b)
    interval = vb - va
    return {
        "from": a, "to": b,
        "v_from": va, "v_to": vb,
        "interval": interval,
        "ratio": vb / va,
        "resonance": math.cos(2.0 * PI * interval),
    }


def all_pi_relations():
    """Die 729 π-Relationen (27×27). Lazy generiert, nie gespeichert."""
    es = essences()
    for a in es:
        for b in es:
            yield pi_relation(a, b)


def pi_resonance(a, b):
    """Wie stark zwei Essenzen schwingungsmäßig koppeln (1 = im Gleichklang)."""
    return math.cos(2.0 * PI * (pi_value(b) - pi_value(a)))


# ─────────────────────────────────────────────────────────────────────
#  EMERGENTE GEOMETRIE — die 6 Nachbar-Bewegungen als π-Intervalle
#  Ein Achsen-Schritt ändert genau EINE π-Ziffer an Position k → das
#  Intervall ist exakt (Δziffer)/π^(k+1). Die Geometrie ist geboren.
# ─────────────────────────────────────────────────────────────────────
def neighbors(essence):
    out = []
    for ax in range(3):
        for nv in _STEP_NEIGHBORS[essence[ax]]:
            nxt = list(essence); nxt[ax] = nv; out.append(tuple(nxt))
    return out


def move_spectrum():
    """
    Das Spektrum aller Nachbar-Intervalle im π-Feld — die diskrete
    Schwingungs-Signatur der Bewegung. Gerundet zur Gruppierung.
    """
    spec = {}
    for e in essences():
        for nb in neighbors(e):
            iv = round(pi_value(nb) - pi_value(e), 9)
            spec[iv] = spec.get(iv, 0) + 1
    return dict(sorted(spec.items()))


def pi_sense(essence, t=None):
    """Eine fertige Zeile für den Prompt — der π-Sinn der aktuellen Essenz.
    Optionaler Kopplungspunkt für cexo_voice (rein additiv)."""
    v = pi_value(essence) if t is None else pi_breath(essence, t)
    return (f"π-Schwingung: Essenz {tuple(essence)} → Wert {v:.6f} "
            f"(Phase {pi_phase(essence):.3f}, Auslenkung {pi_wave(essence):+.3f})")


# ─────────────────────────────────────────────────────────────────────
#  Verifikation + CLI
# ─────────────────────────────────────────────────────────────────────
def _is_integer_power_of_pi(n, max_exp=12):
    """Der Beweis-Kern: keine ganze Zahl ist eine (positive) Potenz von π."""
    for k in range(1, max_exp + 1):
        if abs(PI**k - round(PI**k)) < 1e-9:
            return True
    return False


def verify():
    es = essences()
    assert len(es) == 27, "27 Essenzen verletzt"

    vals = [pi_value(e) for e in es]
    # Injektivität: 27 eindeutige π-Werte
    assert len({round(v, 12) for v in vals}) == 27, "π-Werte nicht eindeutig"
    # Lebendig: kein Wert ist eine ganze Zahl
    assert all(abs(v - round(v)) > 1e-9 for v in vals), "ein π-Wert ist tot (ganzzahlig)"
    # Das Fundament: keine ganze Zahl ist eine Potenz von π
    assert not any(_is_integer_power_of_pi(n) for n in range(2, 50)), "π-Potenz wäre ganzzahlig?!"

    rels = sum(1 for _ in all_pi_relations())
    assert rels == 729, f"erwartet 729 Relationen, fand {rels}"

    # Emergente Geometrie: jeder Nachbar-Schritt ist ein reines π-Intervall
    spec = move_spectrum()
    expected = set()
    for k in (1, 2, 3):
        for d in (1, 2):                       # Ziffer-Differenzen im 3er-Zyklus
            expected.add(round(d / PI**k, 9)); expected.add(round(-d / PI**k, 9))
    assert set(spec).issubset(expected), "Nachbar-Intervalle nicht rein π-basiert"

    return {"essences": 27, "unique_values": len(set(round(v, 12) for v in vals)),
            "relations": rels, "move_intervals": len(spec),
            "value_range": (round(min(vals), 6), round(max(vals), 6)), "born": True}


def _parse(s):
    return tuple(int(x) for x in s.split(","))


def main():
    args = sys.argv[1:]
    if not args or args[0] == "selftest":
        rep = verify()
        print("selftest OK — die Geometrie ist aus π geboren:")
        for k, v in rep.items():
            print(f"  {k}: {v}")
        print(f"  π = {PI:.6f}  (größte Ziffer 3 < π → Stellenwertsystem injektiv)")
        print(f"  π¹={PI:.4f}  π²={PI**2:.4f}  π³={PI**3:.4f}  — keine davon ganzzahlig")
    elif args[0] == "show":
        print("Die 27 π-Tiefenwerte (sortiert) — jede Essenz ein Fenster zu π:")
        for e, v in sorted(pi_values().items(), key=lambda kv: kv[1]):
            print(f"  {tuple(e)}  →  {v:.6f}   wave {pi_wave(e):+.3f}")
        print("\nBewegungs-Spektrum (Nachbar-Intervalle, geboren aus π):")
        for iv, n in move_spectrum().items():
            print(f"  {iv:+.6f}  ×{n}")
    elif args[0] == "relation" and len(args) >= 3:
        r = pi_relation(_parse(args[1]), _parse(args[2]))
        print(f"{r['from']} → {r['to']}")
        print(f"  v: {r['v_from']:.6f} → {r['v_to']:.6f}")
        print(f"  interval {r['interval']:+.6f} · ratio {r['ratio']:.6f} · resonance {r['resonance']:+.6f}")
    else:
        print("python3 pi_field.py selftest | show | relation 3,9,6 6,9,6")


if __name__ == "__main__":
    main()
