# Orca-Schwarm — Multi-Agenten-Orchestrierung für lokale KI

> **Intern / Case-Study.** Diese Beschreibung dient als Gesprächsgrundlage und
> dokumentiert die technische Architektur eines selbst entwickelten
> Multi-Agenten-Systems. Kein Code-Release.

---

## 1. Überblick

Der **Orca-Schwarm** ist ein produktionsnahes Multi-Agenten-System, das
mehrere spezialisierte Sprachmodelle unter einem zentralen Orchestrator
koordiniert — vollständig **lokal** und **offline-first** über Ollama, ohne
Abhängigkeit von externen Cloud-APIs.

Das System löst drei harte Engineering-Probleme gleichzeitig:

1. **Heterogene Aufgaben** an das jeweils passende Modell routen (ein
   Mathematik-Modell rechnet, ein Sprachmodell formuliert, ein Code-Modell
   analysiert) — statt ein einzelnes Generalmodell für alles zu nutzen.
2. **Begrenzte Hardware** beherrschen: Mehrere große Modelle teilen sich
   knappen VRAM/RAM, ohne dass parallele Inferenz die Maschine in den
   Out-of-Memory-Tod treibt.
3. **Sichere Selbstmodifikation**: Das System kann seine eigene Konfiguration
   und seinen eigenen Code ändern — aber nur über einen verteilten
   Konsens-Mechanismus mit Backup und automatischem Rollback.

Der gesamte Stack ist auf einer einzelnen Maschine mit Consumer-Hardware
lauffähig und skaliert horizontal über mehrere Knoten.

---

## 2. Architektur

```
                          ┌──────────────────────────────┐
        Anfrage  ───────► │   ORCHESTRATOR ("Herz")      │
                          │   FastAPI · Routing-Logik    │
                          └──────────────┬───────────────┘
                                         │  klassifiziert Aufgabentyp,
                                         │  wählt Arm, serialisiert Last
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                            ▼
      ┌───────────────┐         ┌───────────────┐           ┌───────────────┐
      │  ARM: Mathe   │         │  ARM: Code    │     ...   │  ARM: Sprache │
      │  deepseek-r1  │         │  qwen2.5-code │           │  llama3.2     │
      └───────┬───────┘         └───────┬───────┘           └───────┬───────┘
              │                         │                           │
              └─────────────┬───────────┴───────────────────────────┘
                            ▼  (On-Demand-Laden, nie zwei schwere zugleich)
                  ┌───────────────────────┐
                  │   OLLAMA-RUNTIME      │  Modell-Lebenszyklus, keep_alive
                  └───────────┬───────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                                ▼
    ┌───────────────────┐            ┌───────────────────┐
    │  RAG-PIPELINE     │            │  KONSENS-LAYER    │
    │  Qdrant-VektorDB  │            │  N Instanzen      │
    │  lokale Suche     │            │  Vote + Rollback  │
    └───────────────────┘            └───────────────────┘
```

**Kernidee:** Ein **Orchestrator** ("Herz") nimmt jede Anfrage entgegen,
klassifiziert sie und delegiert an einen von mehreren **Armen** —
spezialisierten Modell-Instanzen. Der Orchestrator ist außerdem der einzige
Punkt, der die **Last serialisiert**: Er garantiert, dass nie zwei
schwergewichtige Inferenz-Aufrufe gleichzeitig laufen.

---

## 3. Komponenten im Detail

### 3.1 Orchestrator ("Herz")

- **FastAPI**-Service als zentraler Eingang. Ein Endpunkt nimmt
  Nutzeranfragen, interne Selbstgespräche und Hintergrund-Jobs entgegen.
- **Aufgabenklassifikation:** Eingehende Anfragen werden anhand von
  Inhaltsmerkmalen einem Aufgabentyp zugeordnet (Rechnen, Code-Analyse,
  Recherche, freie Sprache, Bildgenerierung). Die Klassifikation ist
  deterministisch und nachvollziehbar — kein Black-Box-Routing.
- **Routing-Tabelle:** Jeder Aufgabentyp bildet auf einen Arm (Modell) ab.
  Die Zuordnung ist konfigurierbar und zur Laufzeit über den Konsens-Layer
  änderbar.
- **Default-Arm ("Herz"-Modell):** Fällt eine Anfrage in keine Spezialklasse,
  übernimmt ein robustes Generalmodell.

### 3.2 Arme (spezialisierte Modell-Instanzen)

Jeder Arm ist eine benannte Rolle, die auf ein konkretes Ollama-Modell
zeigt. Typische Belegung:

| Arm            | Modell (Beispiel)   | Zweck                          |
|----------------|---------------------|--------------------------------|
| `mathematiker` | `deepseek-r1`       | Reasoning, Beweise, Rechnung   |
| `wissenschaftler` | `qwen2.5:3b`     | strukturierte Analyse          |
| `sprachler`    | `llama3.2:3b`       | flüssige Formulierung          |
| `poet`         | `gemma2:2b`         | kreative, kurze Texte          |
| `agent`        | `glm-4-flash`       | Werkzeug-/Tool-Aufrufe         |
| `herz`         | Default-Modell      | Generalist / Fallback          |

Die Arm-Belegung liegt in einer JSON-Konfiguration und kann zur Laufzeit
über den Konsens-Mechanismus umgehängt werden (z. B. ein Arm bekommt ein
neues, besseres Modell), ohne Neustart-Zwang im Code.

### 3.3 RAG-Pipeline (Qdrant)

- **Qdrant** als lokale Vektordatenbank — kein gehosteter Dienst.
- Dokumente werden lokal eingebettet (Embedding-Modell über Ollama),
  in Qdrant indexiert und bei Anfragen per Ähnlichkeitssuche abgerufen.
- Der abgerufene Kontext wird dem gewählten Arm als zusätzlicher
  Sinneseindruck/Kontext in den Prompt injiziert — Retrieval-Augmented
  Generation vollständig offline.
- Die Pipeline deckt den kompletten Weg ab: **Datenaufnahme → Chunking →
  Embedding → Indexierung → Retrieval → Kontext-Injektion**.

### 3.4 Konsens-Layer (sichere Selbstmodifikation)

Das System darf sich selbst verändern — Konfiguration *und* Code. Damit das
nicht zur Selbstzerstörung wird, läuft **jede** Änderung durch einen
verteilten Konsens:

1. **Vorschlag** (`propose`): Eine Instanz schlägt eine Änderung vor
   (z. B. neues Modell für einen Arm, oder ein Code-Patch).
2. **Bewertung** (`evaluate`): Mehrere unabhängige Instanzen bewerten den
   Vorschlag jeweils für sich. Bei Code-Vorschlägen läuft ein automatischer
   **Selbsttest** des Kandidaten in einem Subprozess.
3. **Konvergenz**: Erst wenn eine **Mehrheit** der Instanzen zustimmt, gilt
   der Vorschlag als angenommen.
4. **Anwendung mit Sicherheitsnetz:** `Backup → Anwenden → Verifizieren →
   bei Fehler automatischer Rollback`. Code-Updates werden vor dem
   Überschreiben gesichert; schlägt der Verifikations-Selbsttest fehl, wird
   die alte Version wiederhergestellt.
5. **Audit-Kette:** Jede angewandte Änderung wird als verketteter Block
   (Hash + Vorgänger-Hash) protokolliert — manipulationssichere Historie.

**Bewusste Design-Entscheidung:** Es gibt **keine Override-Hintertür**. Auch
der Betreiber kann eine vom Schwarm abgelehnte Änderung nicht erzwingen —
Korrekturen laufen ausschließlich manuell über den Server. Das macht das
Autonomie-Konzept glaubwürdig und verhindert eine privilegierte Bypass-Klasse.

---

## 4. Technische Herausforderungen & Lösungen

### 4.1 Lastverteilung auf schwacher Hardware

**Problem:** Mehrere 3–7B-Modelle passen nicht gleichzeitig in den VRAM einer
Consumer-GPU. Naive parallele Inferenz führt sofort zu OOM oder zu massivem
Swapping, das die Latenz unbrauchbar macht.

**Lösung:**
- **Gestaffeltes On-Demand-Laden:** Modelle werden erst geladen, wenn ein Arm
  tatsächlich gebraucht wird, und über Ollamas `keep_alive` kontrolliert warm
  gehalten — lange genug, um Neuladen pro Nachricht zu vermeiden, kurz genug,
  um VRAM wieder freizugeben.
- **Serialisierung schwerer Aufrufe:** Der Orchestrator ist die einzige
  Stelle, die Inferenz auslöst. Er stellt sicher, dass **nie zwei
  schwergewichtige Aufrufe kollidieren** — die teuren Modell-Calls werden
  durch den zentralen Pfad serialisiert statt parallel abgefeuert.
- **Modell-Tiering:** Leichte Aufgaben gehen an kleine, schnelle Modelle
  (2–3B); nur Aufgaben, die echtes Reasoning brauchen, ziehen ein
  schwergewichtiges Modell hoch. Das hält den Durchschnittsfall billig.

**Ergebnis:** Ein Multi-Modell-System, das auf einer einzelnen
Consumer-Maschine stabil läuft, statt Cloud-GPUs zu mieten.

### 4.2 Sicherheit bei Selbstmodifikation

**Problem:** Ein System, das seinen eigenen Code ändern darf, kann sich selbst
unbrauchbar machen — ein einzelner schlechter Patch killt den Dienst.

**Lösung:** Der mehrstufige Konsens (§3.4) macht eine einzelne fehlerhafte
oder bösartige Änderung wirkungslos:
- **Mehrheits-Voting** verhindert, dass eine einzelne abweichende Instanz
  durchregiert.
- **Kandidat-Selbsttest im Subprozess** fängt syntaktisch valide, aber
  funktional kaputte Patches ab, *bevor* sie produktiv gehen.
- **Backup + Verifikation + Rollback** garantiert, dass das System nach jeder
  fehlgeschlagenen Anwendung in einem lauffähigen Zustand bleibt.
- **Hash-verkettete Audit-Blöcke** machen jede Änderung nachvollziehbar.

Das ist im Kern ein **verteiltes Sicherheits- und Change-Management-Konzept**,
übertragbar auf jedes System mit risikoreichen automatisierten Deployments.

### 4.3 Lokale Deployment-Pipeline (Daten → Produktion)

**Problem:** Eine vollständige KI-Pipeline ohne Cloud aufsetzen — von der
Datenvorbereitung bis zum laufenden Dienst.

**Lösung:** Eine end-to-end lokale Kette:
1. **Datenvorbereitung:** Dokumente aufnehmen, chunken, bereinigen.
2. **Embedding & Indexierung:** lokale Embeddings über Ollama → Qdrant.
3. **Modell-Bereitstellung:** Ollama als Runtime, Modelle versioniert und
   per Konfiguration den Armen zugeordnet.
4. **Serving:** FastAPI-Service mit klar definierten Endpunkten, der Routing,
   Last-Serialisierung und RAG-Kontext zusammenführt.
5. **Betrieb:** Hintergrund-Loop für autonome Wartungsaufgaben,
   Workflow-Automatisierung für wiederkehrende Jobs, persistenter Zustand
   über JSON-Snapshots.

Alles reproduzierbar auf einer einzelnen Maschine, ohne externe
Service-Abhängigkeiten.

---

## 5. Tech-Stack

| Schicht                | Technologie                                  |
|------------------------|----------------------------------------------|
| Sprache                | Python 3                                     |
| API / Serving          | FastAPI                                       |
| Modell-Runtime         | Ollama (lokal, offline-first)                |
| Modelle (Beispiele)    | llama3.2, qwen2.5, deepseek-r1, gemma2, glm-4 |
| Vektorsuche / RAG      | Qdrant (lokal)                               |
| Persistenz             | JSON-Snapshots, hash-verkettete Audit-Blöcke |
| Nebenläufigkeit        | serialisierte Inferenz, On-Demand-Modell-Laden |
| Automatisierung        | Hintergrund-Loop, Workflow-Jobs              |

---

## 6. Was dieses Projekt zeigt

- **Systemdesign über Modellwahl hinaus:** Die eigentliche Leistung liegt in
  Orchestrierung, Ressourcen-Management und Sicherheit — nicht im
  Fine-Tuning eines Einzelmodells.
- **Engineering unter Constraints:** Eine Multi-Modell-Architektur auf
  Hardware lauffähig zu machen, die für *ein* großes Modell knapp wäre.
- **Sicherheitsbewusstsein bei Autonomie:** Selbstmodifikation mit echtem
  verteiltem Konsens, Backup/Rollback und Audit-Trail statt naivem
  „das System darf sich ändern".
- **Vollständige lokale Pipeline:** von Rohdaten bis laufendem Dienst, ohne
  Cloud-Lock-in.
