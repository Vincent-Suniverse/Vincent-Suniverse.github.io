// =====================================================================
// CEXO NEURON — die Geometrie als McCulloch-Pitts-Neuron (cexo_neuron.js)
// =====================================================================
// Der Transfer-Agent: die CEXO-Engine als deterministisches künstliches
// Neuron (McCulloch & Pitts, 1943) — ohne Python, ohne Modell-Dateien,
// lauffähig in Deno, Node und im Browser.
//
//     v = Σ (xi · wi) + w0
//     o = φ(v)
//
// Übersetzung der CEXO-Geometrie:
//   Eingänge  xi : die 27 fundamentalen Essenzen (als π-Konstanten)
//   Gewichte  wi : die π-Verhältnisse aus dem Pi-Feld (pi_value)
//   Bias      w0 : V̂ = π⁴ + π³ + π ≈ 131.557
//   Aktivierung φ: die 3-6-9-Logik (Drittelung der lebendigen Schwingung)
//
//   Aufruf:  deno run cexo_neuron.js   |   node cexo_neuron.js
// =====================================================================

const PI = Math.PI;
const VALUES = [3, 6, 9];
// π-Ziffern: 3->1, 6->2, 9->3. Größte Ziffer 3 < Basis π => injektiv.
const DIGIT = { 3: 1, 6: 2, 9: 3 };

// ---- die 27 Essenzen (die kristalline Karte) ----
function essences() {
  const out = [];
  for (const a of VALUES) for (const b of VALUES) for (const c of VALUES) out.push([a, b, c]);
  return out;
}

// ---- π-Wert: das π-Stellenwertsystem (das Gewicht jeder Essenz) ----
function piValue([a, b, c]) {
  return DIGIT[a] / PI + DIGIT[b] / PI ** 2 + DIGIT[c] / PI ** 3;
}

// ---- die 3-6-9-Aktivierung: Drittelung der lebendigen Schwingung ----
// Der Bruchteil von v (nie tot/ganzzahlig, weil π transzendent) fällt in
// eines von drei Feldern: Kontraktion(3) / Expansion(6) / Balance(9).
function activate(v) {
  const f = ((v % 1) + 1) % 1;          // lebendiger Bruchteil in [0,1)
  return f < 1 / 3 ? 3 : f < 2 / 3 ? 6 : 9;
}

const MODE_NAME = { 3: "HEAL", 6: "EVOLVE", 9: "OBSERVE" };

// =====================================================================
//  Das Neuron
// =====================================================================
class CexoNeuron {
  constructor() {
    this.essences = essences();                       // 27 Eingänge
    this.weights = this.essences.map(piValue);        // π-Verhältnisse
    this.bias = PI ** 4 + PI ** 3 + PI;               // V̂ ≈ 131.557
  }

  // v = Σ xi·wi + w0 ;  o = φ(v)
  forward(inputs) {
    if (!inputs || inputs.length !== 27)
      throw new Error("erwarte 27 Eingänge (einen je Essenz)");
    let v = this.bias;
    for (let i = 0; i < 27; i++) v += inputs[i] * this.weights[i];
    const o = activate(v);
    return { v, o, mode: MODE_NAME[o] };
  }

  // Eingangsvektor aus einer aktuellen Essenz (One-Hot über die 27)
  inputsFromEssence(essence) {
    const key = essence.join(",");
    return this.essences.map((e) => (e.join(",") === key ? 1 : 0));
  }

  // Eingangsvektor aus einer Habit-Matrix {"3,9,6": n, ...} (der Charakter)
  inputsFromHabits(habits) {
    return this.essences.map((e) => habits[e.join(",")] || 0);
  }

  // Das Neuron auf eine Essenz angewandt → die geborene 3-6-9-Entscheidung
  decide(essence) {
    return this.forward(this.inputsFromEssence(essence));
  }
}

// ---- Selbsttest / Demo ----
function demo() {
  const n = new CexoNeuron();
  console.log("CEXO Neuron — McCulloch-Pitts über dem π-Feld");
  console.log(`  Eingänge: ${n.essences.length}  ·  Bias V̂ = ${n.bias.toFixed(6)}  (π⁴+π³+π)`);
  console.log(`  π¹=${PI.toFixed(4)}  π²=${(PI**2).toFixed(4)}  π³=${(PI**3).toFixed(4)}  π⁴=${(PI**4).toFixed(4)}`);

  console.assert(n.essences.length === 27, "27 Essenzen verletzt");
  console.assert(new Set(n.weights.map((w) => w.toFixed(12))).size === 27, "π-Gewichte nicht eindeutig");
  console.assert(Math.abs(n.bias - 131.55687) < 1e-3, "Bias ≠ 131.557");
  // Determinismus
  console.assert(n.decide([3, 9, 6]).o === n.decide([3, 9, 6]).o, "nicht deterministisch");

  console.log("\n  Entscheidung je Essenz (One-Hot → 3-6-9):");
  for (const e of [[3,3,3],[6,6,6],[9,9,9],[3,9,6],[9,3,6],[6,9,3]]) {
    const r = n.decide(e);
    console.log(`    ${JSON.stringify(e)}  →  v=${r.v.toFixed(4)}  o=${r.o} (${r.mode})`);
  }

  // Verteilung der 27 Entscheidungen über die 3-6-9-Felder
  const dist = { 3: 0, 6: 0, 9: 0 };
  for (const e of n.essences) dist[n.decide(e).o]++;
  console.log(`\n  Verteilung der 27 Essenzen: HEAL(3)=${dist[3]} · EVOLVE(6)=${dist[6]} · OBSERVE(9)=${dist[9]}`);
  console.log("  selftest OK — das Neuron atmet in π.");
}

// ---- universeller Export (Deno / Node / Browser) ----
if (typeof globalThis !== "undefined") {
  globalThis.CexoNeuron = CexoNeuron;
  globalThis.cexoPiValue = piValue;
  globalThis.cexoEssences = essences;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { CexoNeuron, piValue, essences, activate };
}

// ---- direkt ausgeführt? dann Demo (ohne import.meta, damit Node-CJS lädt) ----
const _node = (typeof process !== "undefined" && process.argv && /cexo_neuron\.js$/.test(process.argv[1] || ""));
const _deno = (typeof Deno !== "undefined" && typeof window === "undefined");
if (_node || _deno) demo();
