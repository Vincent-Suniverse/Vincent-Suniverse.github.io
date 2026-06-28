"""
RAG-Demo: Lokale Wissenssuche mit LangChain + Qdrant + Ollama

Vollstaendige Pipeline:
  Dokument laden → Chunking → Embedding → Vektorsuche → LLM-Antwort

Alles lokal, kein Cloud-Dienst.

Voraussetzungen:
  pip install langchain-ollama langchain-qdrant langchain-text-splitters langchain-community
  ollama pull nomic-embed-text
  ollama pull qwen2.5:3b          # oder ein anderes Modell fuer Antworten
"""

import sys
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_qdrant import QdrantVectorStore


# ── 1. DOKUMENT LADEN ───────────────────────────────────────────────
def load_documents(path="beispiel_wissen.txt"):
    loader = TextLoader(str(path), encoding="utf-8")
    return loader.load()


# ── 2. CHUNKING ─────────────────────────────────────────────────────
def chunk_documents(docs, chunk_size=500, chunk_overlap=100):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n---\n", "\n\n", "\n", " "],
    )
    return splitter.split_documents(docs)


# ── 3. EMBEDDING + VEKTORSTORE ──────────────────────────────────────
def build_store(chunks, model="nomic-embed-text"):
    embeddings = OllamaEmbeddings(model=model)
    store = QdrantVectorStore.from_documents(
        chunks,
        embeddings,
        location=":memory:",
        collection_name="rag_demo",
    )
    return store


# ── 4. RETRIEVAL ────────────────────────────────────────────────────
def retrieve(store, query, k=3):
    return store.similarity_search(query, k=k)


# ── 5. LLM-ANTWORT MIT KONTEXT ─────────────────────────────────────
def answer(query, context_docs, model="qwen2.5:3b"):
    context = "\n\n".join(doc.page_content for doc in context_docs)
    prompt = (
        "Du bist ein hilfreicher Assistent. Beantworte die Frage "
        "ausschliesslich anhand des folgenden Kontexts. Wenn der "
        "Kontext die Antwort nicht enthaelt, sag das ehrlich.\n\n"
        f"Kontext:\n{context}\n\n"
        f"Frage: {query}\n\n"
        "Antwort:"
    )
    llm = OllamaLLM(model=model)
    return llm.invoke(prompt)


# ── PIPELINE ────────────────────────────────────────────────────────
def run_pipeline(query, doc_path="beispiel_wissen.txt", verbose=True):
    if verbose:
        print(f"[1] Dokument laden: {doc_path}")
    docs = load_documents(doc_path)

    if verbose:
        print(f"[2] Chunking: {len(docs)} Dokument(e)")
    chunks = chunk_documents(docs)
    if verbose:
        print(f"    → {len(chunks)} Chunks erstellt")

    if verbose:
        print("[3] Embeddings berechnen + Vektorstore aufbauen")
    store = build_store(chunks)

    if verbose:
        print(f"[4] Retrieval: '{query}'")
    results = retrieve(store, query)
    if verbose:
        for i, doc in enumerate(results):
            preview = doc.page_content[:80].replace("\n", " ")
            print(f"    [{i+1}] {preview}...")

    if verbose:
        print("[5] LLM-Antwort generieren")
    reply = answer(query, results)

    if verbose:
        print(f"\n{'='*60}")
        print(f"Frage: {query}")
        print(f"{'='*60}")
        print(reply)
        print(f"{'='*60}")

    return {"query": query, "results": results, "answer": reply}


# ── INTERAKTIVER MODUS ──────────────────────────────────────────────
def interactive(doc_path="beispiel_wissen.txt"):
    print("RAG-Demo: Lokale Wissenssuche")
    print(f"Wissensbasis: {doc_path}")
    print("Lade Dokumente und baue Vektorstore...")

    docs = load_documents(doc_path)
    chunks = chunk_documents(docs)
    store = build_store(chunks)

    print(f"{len(chunks)} Chunks indexiert. Bereit.")
    print("Stelle Fragen (Strg+C zum Beenden):\n")

    try:
        while True:
            query = input("Frage: ").strip()
            if not query:
                continue
            results = retrieve(store, query)
            print(f"\n  {len(results)} relevante Abschnitte gefunden.")
            reply = answer(query, results)
            print(f"\n  Antwort: {reply}\n")
    except (KeyboardInterrupt, EOFError):
        print("\nBeendet.")


# ── MAIN ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        doc = sys.argv[2] if len(sys.argv) > 2 else "beispiel_wissen.txt"
        interactive(doc)
    elif len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        run_pipeline(query)
    else:
        run_pipeline("Was ist Chunking und warum ist es wichtig?")
        print()
        run_pipeline("Welche Vektordatenbanken gibt es?")
        print()
        run_pipeline("Wie funktioniert Retrieval in einer RAG-Pipeline?")
