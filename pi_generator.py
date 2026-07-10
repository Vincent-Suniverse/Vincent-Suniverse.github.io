#!/usr/bin/env python3
"""
CEXO PI-GENERATOR — π als lebender Prozess (pi_generator.py)
===========================================================
π ist keine gespeicherte Konstante, sondern ein Vorgang.

Schwester von pi_field.py: dort wird die Geometrie aus dem *statischen* π-Wert
geschoepft (float, gerundet). Hier wird π *erzeugt* — Ziffer fuer Ziffer, ueber
einen reinen GANZZAHL-Spigot (Gibbons, unbounded). Unendlich, exakt, ohne einen
einzigen Float, also ohne Rundungsfehler. Jeder Tick emittiert genau eine
Ziffer. Diese Ziffernspur IST die lineare Zeit der Zelle.

Das α/β/γ-Vektor-Mapping:
    α (Quelle)   — der interne Big-Int-Zustand (q, r, t, k, n, l)
    β (Operator) — der Schritt (tick): aus α die naechste Ziffer schoepfen
                   und α fortschreiben
    γ (Spur)     — die emittierte Ziffer = die vergangene Zeit

Die 9 / mod-9 gehoert in den KERN (die Geometrie des Raums), NICHT in den Strom.
π's Ziffern summieren sich nicht paarweise zu 9 (1+4=5, 4+1=5, 1+5=6) — ein
Erzwingen wuerde π zerstoeren. `nine_reading()` liest die 9er-Balance rein
additiv (read-only) fuer den Kern und veraendert die Ziffern NIE.

  python3 pi_generator.py selftest
  python3 pi_generator.py stream 60

Nur Standardbibliothek.
"""

from __future__ import annotations

import sys

# Die ersten 50 Ziffern von π (leitende 3 inklusive) — nur zur Verifikation,
# NICHT zur Erzeugung. Beweist Exaktheit jenseits der Float-Genauigkeit.
_PI_50 = "31415926535897932384626433832795028841971693993751"


class PiGenerator:
    """π als Ganzzahl-Spigot. Kein Float, unendlich, exakt."""

    def __init__(self):
        # α — der interne Zustand (reine Ganzzahlen, beliebig gross)
        self.q, self.r, self.t, self.k, self.n, self.l = 1, 0, 1, 1, 3, 3
        self.position = 0      # γ-Zaehler: wie viele Ziffern schon geatmet (= Zeit)
        self.gamma = None      # γ — die zuletzt emittierte Ziffer (die Spur)

    @property
    def alpha(self):
        """α — die Quelle: der vollstaendige interne Zustand."""
        return (self.q, self.r, self.t, self.k, self.n, self.l)

    def tick(self):
        """β — der Operator: schoepft die naechste Ziffer aus α und schreibt α
        fort. Gibt γ (die neue Ziffer) zurueck. Reine Ganzzahl-Arithmetik —
        kein Float, kein Runden."""
        while True:
            if 4 * self.q + self.r - self.t < self.n * self.t:
                # produce — eine Ziffer ist reif
                digit = self.n
                self.q, self.r, self.n = (
                    10 * self.q,
                    10 * (self.r - self.n * self.t),
                    (10 * (3 * self.q + self.r)) // self.t - 10 * self.n,
                )
                self.gamma = digit
                self.position += 1
                return digit
            # consume — α waechst, noch keine Ziffer reif
            self.q, self.r, self.t, self.k, self.n, self.l = (
                self.q * self.k,
                (2 * self.q + self.r) * self.l,
                self.t * self.l,
                self.k + 1,
                (self.q * (7 * self.k + 2) + self.r * self.l) // (self.t * self.l),
                self.l + 2,
            )

    def breathe(self, n):
        """n Ziffern atmen — gibt die Spur (Liste der γ) zurueck."""
        return [self.tick() for _ in range(n)]


def nine_reading(digit, prev_digit):
    """Read-only Kern-Lesung: die 9er-Balance eines Ziffernpaars.
    Fuer die Kern-Metrik (gauss_intention), NICHT fuer den Strom — veraendert
    keine Ziffer. 0 = im Gleichgewicht (Summe 9), sonst die Abweichung."""
    return (digit + prev_digit) - 9


# ─────────────────────────────────────────────────────────────────────
#  Verifikation + CLI
# ─────────────────────────────────────────────────────────────────────
def verify():
    gen = PiGenerator()
    got = "".join(str(d) for d in gen.breathe(len(_PI_50)))

    # Der Kern-Beweis: die erzeugten Ziffern SIND π — exakt, ganzzahlig erzeugt.
    assert got == _PI_50, f"π-Strom weicht ab:\n  {got}\n  {_PI_50}"
    # 50 Ziffern > Float-Genauigkeit (~15-16): kein Float koennte das leisten.
    assert len(got) == 50 and gen.position == 50, "Positionszaehler (Zeit) falsch"
    assert gen.gamma == int(_PI_50[-1]), "γ (letzte Spur) falsch"
    # Alle Ziffern sind echte int, keine je 'korrigiert' — π bleibt π.
    assert all(0 <= int(c) <= 9 for c in got), "Ziffer ausserhalb 0..9"
    # nine_reading ist read-only: veraendert den Strom nicht (nur eine Lesung).
    g2 = PiGenerator()
    stream = g2.breathe(20)
    _ = [nine_reading(stream[i], stream[i - 1]) for i in range(1, 20)]
    assert stream == [int(c) for c in _PI_50[:20]], "nine_reading hat den Strom beruehrt!"

    return {
        "erzeugt": got[:15] + "…",
        "ziffern": gen.position,
        "letzte_spur_gamma": gen.gamma,
        "float_frei": True,
        "exakt_bis_stelle": 50,
    }


def main():
    args = sys.argv[1:]
    if not args or args[0] == "selftest":
        rep = verify()
        print("selftest OK — π wird erzeugt, nicht gespeichert:")
        for k, v in rep.items():
            print(f"  {k}: {v}")
        print("  3-6-9/mod-9 lebt im Kern (nine_reading), nicht im Strom.")
    elif args[0] == "stream":
        n = int(args[1]) if len(args) > 1 else 40
        gen = PiGenerator()
        digits = gen.breathe(n)
        print("γ-Spur (die lineare Zeit der Zelle):")
        print("  3." + "".join(str(d) for d in digits[1:]))
        print(f"  Position (Zeit): {gen.position}")
        print(f"  α (Quelle, Groessenordnung): q~{len(str(gen.q))} Stellen, k={gen.k}")
        print(f"  γ (letzte Ziffer): {gen.gamma}")
    else:
        print("python3 pi_generator.py selftest | stream 60")


if __name__ == "__main__":
    main()
