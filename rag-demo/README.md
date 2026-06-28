# RAG-Demo: Lokale Wissenssuche mit LangChain + Qdrant + Ollama

Eine vollstaendige RAG-Pipeline (Retrieval-Augmented Generation) — lokal,
offline-first, ohne Cloud-APIs.

## Was dieses Projekt zeigt

1. **Dokumente laden** — Textdateien einlesen
2. **Chunking** — Texte in sinnvolle Abschnitte zerlegen
3. **Embedding** — Abschnitte in Vektoren umwandeln (lokal via Ollama)
4. **Vektorsuche** — Qdrant speichert die Vektoren und findet aehnliche
5. **Retrieval + Generation** — relevante Abschnitte an ein LLM geben,
   das daraus eine Antwort formuliert

## Setup

```bash
# 1. Python-Pakete installieren
pip install langchain-ollama langchain-qdrant langchain-text-splitters langchain-community

# 2. Embedding-Modell laden (klein, laeuft auf CPU)
ollama pull nomic-embed-text

# 3. Demo starten
python rag_demo.py
```

Kein Qdrant-Server noetig — laeuft im Speicher oder als lokale Datei.

## Architektur

```
  Dokument (.txt)
       |
  [ Chunking ]          Text in Abschnitte zerlegen
       |
  [ Embedding ]         Abschnitte → Vektoren (Ollama: nomic-embed-text)
       |
  [ Qdrant Store ]      Vektoren speichern + durchsuchen
       |
  [ Query ]             Frage → aehnlichste Abschnitte finden
       |
  [ LLM-Antwort ]       Kontext + Frage → Antwort generieren (Ollama)
```

## Dateien

- `rag_demo.py` — die komplette Pipeline in einem Skript
- `beispiel_wissen.txt` — Beispiel-Wissensbasis
- `requirements.txt` — Python-Abhaengigkeiten
