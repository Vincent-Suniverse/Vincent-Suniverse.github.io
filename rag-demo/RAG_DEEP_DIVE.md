# RAG Deep Dive — Von Null auf Interview

Vincent-Edition. Keine Copy-Paste-Docs, sondern echtes Verstaendnis.
Alles verbunden mit dem was du schon gebaut hast.

---

## Was heisst RAG ueberhaupt?

**R**etrieval-**A**ugmented **G**eneration
= Abruf-erweiterte Erzeugung

Auf Deutsch: Ein LLM (Sprachmodell) das nicht nur aus seinem Training antwortet,
sondern sich vorher relevante Dokumente HOLT und daraus antwortet.

Warum? Weil ein LLM nur weiss was es im Training gesehen hat. Wenn du willst
dass es ueber DEINE Firmendokumente, DEINE Wissensbasis spricht, musst du ihm
die relevanten Stuecke zur Laufzeit geben. Das ist RAG.

**Brücke zu deiner Arbeit:** Dein Orca bekommt in build_prompt() Kontext
mitgegeben — Terrain-Biografie, Uncertainty, Sphere-State. Das IST konzeptionell
RAG: dem Modell zur Laufzeit Kontext geben den es nicht aus dem Training kennt.

---

## Die RAG-Pipeline — Schritt fuer Schritt

Stell dir vor du hast 500 Seiten Firmendokumentation und jemand fragt:
"Wie kuendige ich meinen Vertrag?"

Das LLM kennt die Antwort nicht — es hat die Dokumente nie gesehen.
RAG loest das in 5 Schritten:

### Schritt 1: LADEN (Document Loading)

Die Dokumente muessen erstmal ins System. Egal ob PDF, Word, Webseite,
Datenbank — alles wird zu Text gemacht.

LangChain hat dafuer "Loader":
- TextLoader — fuer .txt Dateien
- PyPDFLoader — fuer PDFs
- WebBaseLoader — fuer Webseiten
- CSVLoader — fuer Tabellen

**Was du gebaut hast:** In rag_demo.py Zeile 25-27:
```python
loader = TextLoader(str(path), encoding="utf-8")
return loader.load()
```
Das ist Document Loading. Fertig. Du kannst es.

### Schritt 2: CHUNKING (Text in Stuecke schneiden)

Problem: Dein 500-Seiten-Dokument passt nicht komplett ins LLM.
Und selbst wenn — du willst nicht 500 Seiten durchsuchen wenn die
Antwort auf Seite 347 steht.

Also schneidest du den Text in kleine Stuecke — **Chunks**.

**Chunk** = Ein Textstueck, typisch 500-1000 Zeichen.

**Warum nicht einfach alle 500 Zeichen abschneiden?**
Weil du mitten im Satz schneiden wuerdest. Deshalb gibt es Strategien:

**RecursiveCharacterTextSplitter** — der Standard:
- Versucht erst nach Absaetzen zu trennen (\n\n)
- Wenn der Chunk dann immer noch zu gross ist, nach Zeilen (\n)
- Dann nach Saetzen (. )
- Dann nach Woertern ( )
- Rekursiv = er probiert die beste Trennung auf jeder Ebene

**Overlap** (Ueberlappung): Die Chunks ueberlappen sich um z.B. 100 Zeichen.
Warum? Damit Kontext an der Schnittstelle nicht verloren geht.
Stell dir vor ein wichtiger Satz steht genau an der Grenze — mit Overlap
ist er in beiden Chunks drin.

**Was du gebaut hast:** In rag_demo.py Zeile 31-37:
```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n---\n", "\n\n", "\n", " "],
)
```
Genau das. Du hast sogar eigene Separatoren definiert. Das ist nicht Junior.

**Andere Chunking-Strategien (fuer Interview-Wissen):**
- **Semantic Chunking** — schneidet nach inhaltlichen Grenzen, nicht nach Zeichen.
  Nutzt ein Embedding-Modell um zu erkennen wo sich das Thema aendert.
- **Parent Document Retriever** — speichert kleine Chunks fuer die Suche,
  gibt aber den grossen Eltern-Chunk ans LLM. Beste Praezision bei der Suche,
  maximaler Kontext bei der Antwort.

### Schritt 3: EMBEDDING (Text wird zu Zahlen)

Jetzt kommt der Kern. Dein Computer kann nicht "aehnliche Bedeutung" verstehen.
Er braucht Zahlen. Ein **Embedding** wandelt Text in einen Vektor um — eine
Liste von Zahlen (z.B. 768 Stueck), die die BEDEUTUNG codieren.

**Embedding** = Text -> Zahlenvektor (z.B. [0.12, -0.45, 0.78, ...] x 768)

Der Trick: Texte mit aehnlicher Bedeutung haben aehnliche Vektoren.
"Hund" und "Welpe" haben fast den gleichen Vektor.
"Hund" und "Steuererklarung" haben komplett verschiedene Vektoren.

**Embedding-Modell** = Das Modell das diese Umwandlung macht.
Das ist NICHT das gleiche wie das LLM das Antworten generiert!
- Embedding-Modell: klein, schnell, wandelt Text in Zahlen um
  (z.B. nomic-embed-text, 274 MB)
- LLM: gross, langsam, generiert Text
  (z.B. qwen2.5:3b, dein Orca)

**Was du gebaut hast:** In rag_demo.py Zeile 41-42:
```python
embeddings = OllamaEmbeddings(model="nomic-embed-text")
```

**Brücke:** Embeddings sind wie die Signale in deinem Orca.
Signal = [depth: +2, reaction: -1, operation: +1, intuition: 0]
Embedding = [0.12, -0.45, 0.78, ...] x 768
Beides codiert Bedeutung als Zahlen. Gleiche Idee, andere Skala.

### Schritt 4: VECTOR STORE (Speicher fuer die Zahlenvektoren)

Du hast jetzt hunderte Chunks, jeder als Vektor. Die muessen irgendwo
gespeichert werden, und du musst schnell den aehnlichsten finden koennen.

**Vector Store** (Vektordatenbank) = Eine Datenbank die auf Vektoren
optimiert ist. Statt "finde das exakte Wort" macht sie "finde den
Vektor der am naechsten dran ist" (**Similarity Search**).

**Wie funktioniert Aehnlichkeitssuche?**
Cosine Similarity — misst den Winkel zwischen zwei Vektoren.
- Winkel 0 = identisch (Cosine = 1)
- Winkel 90 = komplett verschieden (Cosine = 0)
- Du suchst die Chunks mit dem kleinsten Winkel zu deiner Frage

**Populaere Vector Stores:**
- **Qdrant** — Open Source, lokal oder Cloud, sehr schnell.
  Das nutzt du in deiner Demo.
- **ChromaDB** — sehr einfach, gut fuer Prototypen
- **Pinecone** — Cloud-basiert, skalierbar, kostet Geld
- **pgvector** — PostgreSQL-Erweiterung, gut wenn du schon Postgres nutzt
- **FAISS** — von Meta/Facebook, sehr schnell, nur lokal
- **Weaviate** — Open Source, viele Integrationen

**Was du gebaut hast:** In rag_demo.py Zeile 43-48:
```python
store = QdrantVectorStore.from_documents(
    chunks,
    embeddings,
    location=":memory:",       # im RAM, kein externer Server
    collection_name="rag_demo",
)
```

**Brücke:** Dein sphere_state.json IST ein Vector Store — nur manuell gebaut.
Du speicherst Positionen im {3,6,9}-Raum und suchst nach Naehe (Habits,
Terrain). Gleiche Idee, anderes Format.

### Schritt 5: RETRIEVAL (Die relevanten Stuecke finden)

Jetzt kommt die Frage rein: "Wie kuendige ich meinen Vertrag?"

1. Die Frage wird durch dasselbe Embedding-Modell geschickt -> Fragevektor
2. Der Fragevektor wird gegen alle gespeicherten Chunk-Vektoren verglichen
3. Die k aehnlichsten Chunks werden zurueckgegeben (typisch k=3 bis k=5)

**Wichtige Parameter:**
- **k** — wie viele Ergebnisse? Mehr = mehr Kontext aber auch mehr Rauschen
- **Score Threshold** — Mindest-Aehnlichkeit, filtert irrelevante Ergebnisse raus

**Was du gebaut hast:** In rag_demo.py Zeile 53-54:
```python
def retrieve(store, query, k=3):
    return store.similarity_search(query, k=k)
```

**Fortgeschrittene Retrieval-Strategien (Interview-Wissen):**

- **Hybrid Search** — kombiniert Vektorsuche (semantisch) mit klassischer
  Textsuche (Keyword). Fuer Fachbegriffe die semantisch nicht gut erkannt
  werden. Beispiel: "KSchG" findet Vektorsuche vielleicht nicht, aber
  Keyword-Suche schon.

- **Reranking** — nach dem ersten Retrieval laesst du ein ZWEITES Modell
  (Cross-Encoder) die Ergebnisse nochmal sortieren. Der Cross-Encoder ist
  langsamer aber praeziser als Cosine Similarity. Erst grob finden (schnell),
  dann fein sortieren (genau).

- **Multi-Query Retrieval** — das LLM formuliert die Frage auf 3-4
  verschiedene Arten um und sucht mit jeder Variante. Findet mehr
  relevante Chunks weil verschiedene Formulierungen verschiedene Treffer
  liefern.

- **Parent Document Retriever** — sucht mit kleinen Chunks (praezise Treffer),
  gibt aber den grossen Eltern-Abschnitt ans LLM (voller Kontext).

### Schritt 6: GENERATION (LLM antwortet mit Kontext)

Die gefundenen Chunks werden zusammen mit der Frage in einen Prompt gepackt:

"Hier ist Kontext: [Chunk 1] [Chunk 2] [Chunk 3]
Frage: Wie kuendige ich meinen Vertrag?
Antworte nur basierend auf dem Kontext."

Das LLM liest den Kontext und generiert eine Antwort die auf ECHTEN
Dokumenten basiert — nicht auf Training-Halluzinationen.

**Was du gebaut hast:** In rag_demo.py Zeile 58-69:
```python
context = "\n\n".join(doc.page_content for doc in context_docs)
prompt = (
    "Du bist ein hilfreicher Assistent. Beantworte die Frage "
    "ausschliesslich anhand des folgenden Kontexts..."
)
llm = OllamaLLM(model=model)
return llm.invoke(prompt)
```

---

## LangChain — Das Framework das alles zusammenklebt

LangChain ist wie ein Baukasten. Jeder Schritt oben hat eine LangChain-Klasse.
Du kannst die Teile austauschen ohne den Rest umzuschreiben.

### Die wichtigsten LangChain-Konzepte:

**Chain** = Eine Kette von Schritten. Input geht rein, wird durch mehrere
Schritte verarbeitet, Output kommt raus.
Frueherer Stil: LLMChain, RetrievalQAChain.
Aktueller Stil: LCEL (s.u.).

**Agent** = Ein LLM das SELBST entscheidet welches Tool es nutzt.
Statt einer festen Kette (immer A dann B dann C) sagt das LLM:
"Fuer diese Frage brauche ich erst das Suchtool, dann den Taschenrechner."
**Brücke:** Genau wie dein Orca mit Arms — er entscheidet selbst ob er
[arm:denken] oder [arm:mund] nutzt.

**Tool** = Eine Funktion die ein Agent aufrufen kann.
Suche, Taschenrechner, Datenbank-Abfrage, API-Call.
**Brücke:** Deine Arms sind Tools. Mund, Denken, Auge — alles Tools
die der Agent waehlen kann.

**Prompt Template** = Eine Vorlage mit Platzhaltern.
```
"Beantworte {question} basierend auf {context}"
```
Wird zur Laufzeit mit echten Werten gefuellt.
**Brücke:** Dein build_prompt() in cexo_voice.py IST ein Prompt Template.

**LCEL (LangChain Expression Language)** = Die aktuelle Art Chains zu bauen.
Pipe-Syntax mit dem | Operator:

```python
chain = retriever | prompt | llm | output_parser
```

Liest sich wie eine Unix-Pipe: Retriever-Ergebnis -> in den Prompt ->
ins LLM -> Output parsen. Sauber, kurz, komponierbar.

Wenn sie im Interview fragen "kennen Sie LCEL?" sagst du:
"Ja, die Pipe-Syntax fuer Chains. Retriever pipe Prompt pipe LLM.
Ich hab bisher funktional gearbeitet aber das Konzept ist klar."

### LangChain-Pakete (aktuell):

- **langchain-core** — Basisklassen, Interfaces, LCEL
- **langchain-ollama** — Ollama-Anbindung (lokal)
- **langchain-openai** — OpenAI-Anbindung (Cloud)
- **langchain-qdrant** — Qdrant Vector Store
- **langchain-chroma** — ChromaDB Vector Store
- **langchain-text-splitters** — Chunking-Strategien
- **langchain-community** — Loader, Tools, Integrationen

---

## Evaluation — Wie misst man ob RAG gut funktioniert?

Das ist Interview-Gold. Jeder kann eine RAG-Pipeline bauen.
Die Frage ist: woher weisst du ob sie GUT ist?

### RAGAS Framework

RAGAS = **R**etrieval **A**ugmented **G**eneration **A**ssessment

Vier Metriken:

1. **Faithfulness** (Treue) — Antwortet das LLM nur mit dem was im
   Kontext steht? Oder halluziniert es dazu?
   Hoch = gut (bleibt bei den Fakten)

2. **Answer Relevancy** (Antwort-Relevanz) — Ist die Antwort relevant
   fuer die Frage? Oder labert es am Thema vorbei?
   Hoch = gut (trifft die Frage)

3. **Context Precision** (Kontext-Praezision) — Sind die geholten Chunks
   wirklich relevant? Oder ist Muell dabei?
   Hoch = gut (Retrieval findet das Richtige)

4. **Context Recall** (Kontext-Abdeckung) — Wurden ALLE relevanten
   Chunks gefunden? Oder fehlen wichtige?
   Hoch = gut (nichts Wichtiges uebersehen)

**Fuer Interview:** "Ich wuerde RAGAS einsetzen um die Pipeline zu
evaluieren — Faithfulness gegen Halluzinationen, Context Precision
fuer Retrieval-Qualitaet, und Recall um sicherzustellen dass nichts
Wichtiges fehlt."

---

## Deployment — Wie kommt die Pipeline in Produktion?

### FastAPI
Python-Framework fuer REST-APIs. Dein RAG wird ein Webservice:
```python
@app.post("/frage")
def frage(query: str):
    ergebnis = rag_pipeline(query)
    return {"antwort": ergebnis}
```

**Brücke:** Dein Orca laeuft bereits als Server (serve-Modus mit
Flask/HTTP). FastAPI ist das Gleiche, nur moderner und schneller.

### Docker
Packt deine ganze Anwendung in einen Container — Python, Abhaengigkeiten,
Modelle, alles drin. Laeuft ueberall gleich.

**Fuer Interview:** "Ich wuerde die Pipeline als Docker-Container
deployen mit FastAPI als API-Layer und Qdrant als separatem Container
fuer den Vector Store."

### Monitoring
In Produktion willst du sehen:
- Welche Fragen kommen rein?
- Wie gut sind die Retrieval-Ergebnisse?
- Wo halluziniert das LLM?
- Wie lang dauert eine Antwort?

Tools: LangSmith (von LangChain), Weights & Biases, eigenes Logging.

---

## DSGVO / Datenschutz — Dein Alleinstellungsmerkmal

Deutsche Firmen (Mittelstand!) haben ANGST vor Cloud-AI wegen Datenschutz.
Wenn du sagst "ich baue alles lokal, on-premise, keine Daten verlassen
den Server" — das ist Gold wert.

**Dein Stack ist perfekt dafuer:**
- Ollama = lokale Inference, keine Cloud
- Qdrant im Memory-Modus = keine externe Datenbank
- Alles auf eigenem Server = DSGVO-konform by design

**Fuer Interview:** "Mein Ansatz ist privacy-by-design. Alle Modelle
laufen lokal ueber Ollama, der Vector Store laeuft on-premise, keine
Daten gehen nach aussen. Das ist fuer den deutschen Mittelstand
entscheidend."

---

## Zusammenfassung — Die ganze Pipeline in einem Satz

**Dokument laden -> in Chunks schneiden -> Chunks zu Vektoren machen ->
Vektoren speichern -> bei Frage die aehnlichsten Chunks finden ->
Chunks + Frage ans LLM -> Antwort die auf echten Dokumenten basiert.**

Das ist RAG. Das hast du gebaut. Jetzt kennst du die Woerter dafuer.

---

## Spickzettel fuer Interview (eine Seite)

```
RAG = Retrieval-Augmented Generation (Abruf-erweiterte Erzeugung)

PIPELINE:
  Load -> Chunk -> Embed -> Store -> Retrieve -> Generate

CHUNKING:
  RecursiveCharacterTextSplitter (Standard)
  Semantic Chunking (nach Inhalt trennen)
  Overlap = Ueberlappung damit Kontext nicht verloren geht

EMBEDDING:
  Text -> Zahlenvektor (768 Dimensionen typisch)
  nomic-embed-text (lokal, 274 MB)
  Aehnliche Bedeutung = aehnlicher Vektor

VECTOR STORE:
  Qdrant, ChromaDB, Pinecone, pgvector, FAISS, Weaviate
  Cosine Similarity = Winkel zwischen Vektoren messen

RETRIEVAL:
  Similarity Search (Standard)
  Hybrid Search (Vektor + Keyword)
  Reranking (Cross-Encoder nachsortieren)
  Multi-Query (Frage umformulieren)

LANGCHAIN:
  Chain = Kette von Schritten
  Agent = LLM entscheidet selbst welches Tool
  Tool = Funktion die Agent aufrufen kann
  LCEL = Pipe-Syntax: retriever | prompt | llm | parser

EVALUATION:
  RAGAS (Faithfulness, Relevancy, Precision, Recall)

DEPLOYMENT:
  FastAPI + Docker + Qdrant Container

DSGVO:
  Alles lokal, Ollama, on-premise, privacy-by-design
```
