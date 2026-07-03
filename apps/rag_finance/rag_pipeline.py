# rag.py
# Config-driven RAG pipeline for finance documents.
# Uses sentence-transformers for embeddings, ChromaDB for vector store, Ollama for generation.

import os
import json
import glob
import shutil
import chromadb
from sentence_transformers import SentenceTransformer

# ── Globals ──────────────────────────────────────────────────────────────────
CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"

_embed_model = None


def _get_embed_model():
    """Lazy-load the sentence-transformer model."""
    global _embed_model
    if _embed_model is None:
        print(f"Loading embedding model ('{EMBED_MODEL_NAME}')...")
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


# ── Config helpers ───────────────────────────────────────────────────────────
def load_config(path: str = None) -> dict:
    """Load RAG config from a JSON file."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict, path: str = None):
    """Save RAG config to a JSON file."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ── Chunking ─────────────────────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = 200, chunk_overlap: int = 20) -> list[str]:
    """Split text into overlapping character-level chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return [c.strip() for c in chunks if c.strip()]


def load_corpus(chunk_size: int = 200, chunk_overlap: int = 20) -> tuple[list[str], list[dict]]:
    """Load all .txt files from documents/ and chunk them by paragraph. Returns (chunks, metadatas)."""
    all_chunks = []
    all_metas = []
    txt_files = sorted(glob.glob(os.path.join(CORPUS_DIR, "*.txt")))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {CORPUS_DIR}")
    
    for filepath in txt_files:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
            
        paragraphs = text.split("\n\n")
        current_section = "Introduction"
        
        for p_idx, p in enumerate(paragraphs):
            p_clean = p.strip()
            if not p_clean:
                continue
                
            # Update section header if paragraph matches header heuristic
            lines = p_clean.split("\n")
            if len(lines) == 1 and len(p_clean) < 100 and (p_clean.endswith(":") or p_clean.isupper() or p_clean.endswith("Guide") or p_clean.endswith("Circular")):
                current_section = p_clean.rstrip(":")
                
            # Chunk the paragraph text
            p_chunks = chunk_text(p_clean, chunk_size, chunk_overlap)
            for chunk in p_chunks:
                all_chunks.append(chunk)
                all_metas.append({
                    "source": filename,
                    "section": current_section,
                    "paragraph_index": p_idx
                })
                
    print(f"Loaded {len(all_chunks)} chunks from {len(txt_files)} files.")
    return all_chunks, all_metas


# ── Indexing ─────────────────────────────────────────────────────────────────
def build_index(chunk_size: int = 200, chunk_overlap: int = 20):
    """Build (or rebuild) the ChromaDB vector index from corpus files."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    
    collection = client.get_or_create_collection("finance_docs")
    
    # Clean old documents in a single atomic step to avoid stale cached UUIDs
    try:
        existing = collection.get()
        if existing and "ids" in existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception as e:
        print(f"Warning clearing collection: {e}")
        
    chunks, metas = load_corpus(chunk_size, chunk_overlap)
    model = _get_embed_model()
    embeddings = model.encode(chunks, show_progress_bar=False).tolist()

    ids = [f"chunk_{i}" for i in range(len(chunks))]
    collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metas)
    print(f"Index built: {len(chunks)} chunks indexed.")


# ── Retrieval ────────────────────────────────────────────────────────────────
def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve the top-k most relevant chunks for a query."""
    model = _get_embed_model()
    query_embedding = model.encode([query], show_progress_bar=False).tolist()

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection("finance_docs")
    results = collection.query(query_embeddings=query_embedding, n_results=top_k)

    retrieved = []
    for i in range(len(results["documents"][0])):
        meta = results["metadatas"][0][i]
        retrieved.append({
            "text": results["documents"][0][i],
            "source": meta.get("source", "unknown"),
            "section": meta.get("section", "Introduction"),
            "paragraph_index": meta.get("paragraph_index", 0),
            "distance": results["distances"][0][i] if results.get("distances") else None,
        })
    return retrieved


# ── Generation (Ollama) ─────────────────────────────────────────────────────
def generate(query: str, chunks: list[dict], prompt_template: str, temperature: float = 0.0) -> str:
    """Generate an answer using Ollama (local LLM) with retrieved context."""
    import urllib.request

    context_items = []
    for c in chunks:
        context_items.append(f"Source: {c['source']}, Section: {c['section']} (Paragraph {c['paragraph_index'] + 1})\nContent: {c['text']}")
    context = "\n\n".join(context_items)
    
    prompt = prompt_template.replace("{context}", context).replace("{question}", query)

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode())
            return body.get("response", "").strip()
    except Exception as e:
        print(f"Ollama generation error: {e}")
        return f"Error: {e}"


# ── High-level query ─────────────────────────────────────────────────────────
def query(question: str, config: dict = None) -> dict:
    """End-to-end RAG query: retrieve context then generate answer."""
    if config is None:
        config = load_config()

    chunks = retrieve(question, top_k=int(config.get("top_k", 3)))
    answer = generate(
        query=question,
        chunks=chunks,
        prompt_template=config.get("prompt_template", "Context: {context}\n\nQuestion: {question}\n\nAnswer:"),
        temperature=float(config.get("temperature", 0.0)),
    )
    return {
        "question": question,
        "answer": answer,
        "sources": chunks,
        "config_used": config,
    }


# ── CLI test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg = load_config()
    print("Building index...")
    build_index(chunk_size=int(cfg["chunk_size"]), chunk_overlap=int(cfg["chunk_overlap"]))
    print("\nAsking: 'What is the repo rate?'")
    result = query("What is the repo rate?", cfg)
    print(f"\nAnswer: {result['answer']}")
    print(f"\nSources:")
    for s in result["sources"]:
        print(f"  - {s['source']}: {s['text'][:80]}...")
