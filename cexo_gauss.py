#!/usr/bin/env python3
"""
CEXO GAUSS-NEURON — Prototyp (cexo_gauss.py)
============================================
Vom harten Schalter zur weichen Intention.

Das McCulloch-Pitts-Neuron (cexo_neuron.js) entscheidet hart: φ(v) → 3/6/9.
Dieses Gauß-Neuron bildet die drei Zustände 3, 6, 9 NICHT als harte Stufen
ab, sondern als drei ÜBERLAPPENDE Gauß-Glocken. Die Ausgabe ist kein
binärer Wert, sondern eine INTENTION — ein Vektor über (HEAL, EVOLVE, OBSERVE).
So kann der Orca zwischen Zuständen liegen, Muster verbinden und „wissen",
wann er sich seiner Sache sicher ist und wann nicht.

Glockenbreite — der π²-Blickwinkel (Theorem 4):
    Varianz σ² = π² ≈ 9.8696   →   σ = π
    Bei Zentren 3, 6, 9 (Abstand 3) überlappen die Glocken stark:
    eine lebendige, weiche Membran statt drei getrennter Fächer.

Deterministisch, nur Standardbibliothek. Sofort testbar:
    python3 cexo_gauss.py            # Demo + Selbsttest
    python3 cexo_gauss.py 3 9 6      # Intention einer Essenz
"""

from __future__ import annotations

import math
import sys

PI = math.pi
CENTERS = (3, 6, 9)                     # die drei Zustände als Glocken-Zentren
NAMES = {3: "HEAL", 6: "EVOLVE", 9: "OBSERVE"}
VAR = PI ** 2                           # σ² = π²  — der π²-Blickwinkel (Theorem 4)
SIGMA = math.sqrt(VAR)                  # = π


def bell(x: float, mu: float, var: float = VAR) -> float:
    """Eine Gauß-Glocke: wie sehr 'gehört' x zum Zustand mu."""
    return math.exp(-((x - mu) ** 2) / (2.0 * var))


class GaussNeuron:
    """
    Nimmt ein Signal (Skalar oder Essenz) und gibt eine INTENTION zurück —
    einen normierten Vektor über (3, 6, 9). Keine harte Entscheidung.
    """

    def __init__(self, var: float = VAR, centers=CENTERS):
        self.var = var
        self.centers = tuple(centers)

    # ---- ein Signal → Intention ----
    def intention(self, x: float) -> dict:
        raw = {c: bell(x, c, self.var) for c in self.centers}
        s = sum(raw.values()) or 1.0
        return {c: raw[c] / s for c in self.centers}

    # ---- Essenz (3 Achsen) → ein Signal x in [3,9] ----
    @staticmethod
    def _to_x(sig) -> float:
        if isinstance(sig, (list, tuple)):
            return sum(sig) / len(sig)
        return float(sig)

    def forward(self, sig) -> dict:
        x = self._to_x(sig)
        inten = self.intention(x)
        vector = [round(inten[c], 4) for c in self.centers]
        dominant = max(inten, key=inten.get)
        return {
            "x": round(x, 4),
            "intention": {NAMES[c]: round(inten[c], 4) for c in self.centers},
            "vector": vector,                       # [HEAL, EVOLVE, OBSERVE]
            "dominant": NAMES[dominant],
            "confidence": round(max(inten.values()), 4),
            "entropy": round(self._entropy(inten), 4),   # 0=sicher, 1=völlig gemischt
        }

    # ---- mehrere Signale → eine fusionierte Intention (Muster verbinden) ----
    def combine(self, signals) -> dict:
        acc = {c: 0.0 for c in self.centers}
        for sig in signals:
            inten = self.intention(self._to_x(sig))
            for c in self.centers:
                acc[c] += inten[c]
        s = sum(acc.values()) or 1.0
        fused = {c: acc[c] / s for c in self.centers}
        dominant = max(fused, key=fused.get)
        return {
            "intention": {NAMES[c]: round(fused[c], 4) for c in self.centers},
            "vector": [round(fused[c], 4) for c in self.centers],
            "dominant": NAMES[dominant],
            "entropy": round(self._entropy(fused), 4),
        }

    @staticmethod
    def _entropy(inten: dict) -> float:
        n = len(inten)
        h = -sum(p * math.log(p) for p in inten.values() if p > 0)
        return h / math.log(n) if n > 1 else 0.0


def _selftest():
    g = GaussNeuron()
    assert abs(VAR - 9.8696) < 1e-3, "π²-Breite falsch"
    # reine Zustände → dominante, aber NICHT harte Intention (Überlappung!)
    for v in CENTERS:
        r = g.forward([v, v, v])
        assert r["dominant"] == NAMES[v], f"{v} sollte {NAMES[v]} dominieren"
        assert r["confidence"] < 1.0, "Glocken überlappen → nie 100% hart"
    # Vektor ist normiert (Summe ~1) → echte Intention, kein binärer Wert
    s = sum(g.forward(6)["vector"])
    assert abs(s - 1.0) < 1e-6, "Intention nicht normiert"
    # zwischen zwei Zuständen → hohe Entropie (er weiß, dass er unsicher ist)
    mid = g.forward(4.5)
    assert mid["entropy"] > g.forward(3)["entropy"], "Zwischenlage sollte unsicherer sein"
    print("selftest OK — weiche Intention, π²-Breite, normierte Vektoren.")


def _demo():
    g = GaussNeuron()
    print("CEXO Gauß-Neuron — 3·6·9 als überlappende Glocken")
    print(f"  π²-Blickwinkel (Theorem 4): σ² = {VAR:.4f}  (σ = π = {SIGMA:.4f})\n")
    print("  Glockenwerte über das Feld (3 … 9):")
    for x in (3, 4, 4.5, 5, 6, 7, 8, 9):
        b = [f"{NAMES[c]} {bell(x,c):.2f}" for c in CENTERS]
        print(f"    x={x:>4}:  " + " · ".join(b))
    print("\n  Intention einzelner Essenzen:")
    for e in [[3,3,3],[9,9,9],[3,9,6],[6,6,3],[9,3,6]]:
        r = g.forward(e)
        print(f"    {e} → x={r['x']:<5} {r['dominant']:7s} "
              f"vec={r['vector']} entropie={r['entropy']}")
    print("\n  Muster verbinden (combine) — drei Essenzen zu einer Intention:")
    r = g.combine([[3,3,3],[3,6,3],[6,6,9]])
    print(f"    → {r['dominant']}  vec={r['vector']}  entropie={r['entropy']}")
    _selftest()


def main():
    args = sys.argv[1:]
    if args and all(a.lstrip("-").isdigit() for a in args):
        g = GaussNeuron()
        import json
        print(json.dumps(g.forward([int(a) for a in args]), ensure_ascii=False, indent=2))
    else:
        _demo()


if __name__ == "__main__":
    main()
