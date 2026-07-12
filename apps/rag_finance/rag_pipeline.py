# rag.py
# Config-driven RAG pipeline for finance documents.
# Uses sentence-transformers for embeddings, ChromaDB for vector store, Ollama for generation.

import os
import re
import json
import glob
import shutil
import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

# ── Globals ──────────────────────────────────────────────────────────────────
CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = "qwen2.5:1.5b"

_embed_model = None

# BM25 index globals (rebuilt on each build_index call)
_bm25_index = None
_bm25_corpus_chunks = []   # list of chunk text strings
_bm25_corpus_metas = []    # list of metadata dicts (source, section, paragraph_index)
_bm25_tokenized = []       # tokenized version for BM25


def _get_embed_model():
    """Lazy-load the sentence-transformer model."""
    global _embed_model
    if _embed_model is None:
        print(f"Loading embedding model ('{EMBED_MODEL_NAME}')...")
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def _tokenize(text: str) -> list:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r'\w+', text.lower())


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
    """Build (or rebuild) the ChromaDB vector index and BM25 keyword index from corpus files."""
    global _bm25_index, _bm25_corpus_chunks, _bm25_corpus_metas, _bm25_tokenized
    
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
    
    # Build BM25 index from the same chunks
    _bm25_corpus_chunks = chunks
    _bm25_corpus_metas = metas
    _bm25_tokenized = [_tokenize(t) for t in chunks]
    if _bm25_tokenized:
        _bm25_index = BM25Okapi(_bm25_tokenized)
    else:
        _bm25_index = None
    
    print(f"Index built: {len(chunks)} chunks indexed.")


# ── Retrieval ────────────────────────────────────────────────────────────────
def retrieve_vector(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve the top-k most relevant chunks using vector similarity."""
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


def retrieve_bm25(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve the top-k most relevant chunks using BM25 keyword matching."""
    global _bm25_index, _bm25_corpus_chunks, _bm25_corpus_metas
    
    if _bm25_index is None or not _bm25_corpus_chunks:
        return []
    
    tokenized_query = _tokenize(query)
    scores = _bm25_index.get_scores(tokenized_query)
    
    # Get top-k indices sorted by score descending
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    
    retrieved = []
    for i in top_indices:
        if scores[i] > 0:
            meta = _bm25_corpus_metas[i]
            retrieved.append({
                "text": _bm25_corpus_chunks[i],
                "source": meta.get("source", "unknown"),
                "section": meta.get("section", "Introduction"),
                "paragraph_index": meta.get("paragraph_index", 0),
                "distance": round(1.0 / (1.0 + scores[i]), 4),  # Convert BM25 score to distance-like metric
            })
    return retrieved


def retrieve_hybrid(query: str, top_k: int = 3) -> list[dict]:
    """
    Hybrid retrieval using Reciprocal Rank Fusion (RRF).
    Runs both vector search and BM25, fuses results using RRF formula:
      score(doc) = sum(1 / (k + rank)) across retrievers
    """
    RRF_K = 60  # Standard RRF constant
    
    # Fetch more candidates from each retriever, then fuse down to top_k
    fetch_k = min(top_k * 2, 20)
    
    vector_results = retrieve_vector(query, fetch_k)
    bm25_results = retrieve_bm25(query, fetch_k)
    
    # Compute RRF scores using text prefix as dedup key
    rrf_scores = {}
    doc_map = {}
    
    for rank, doc in enumerate(vector_results):
        doc_key = doc["text"][:200]
        rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + 1.0 / (RRF_K + rank + 1)
        if doc_key not in doc_map:
            doc_map[doc_key] = doc
    
    for rank, doc in enumerate(bm25_results):
        doc_key = doc["text"][:200]
        rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + 1.0 / (RRF_K + rank + 1)
        if doc_key not in doc_map:
            doc_map[doc_key] = doc
    
    # Sort by RRF score and return top_k
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)[:top_k]
    
    return [doc_map[k] for k in sorted_keys]


def retrieve(query: str, top_k: int = 3, strategy: str = "vector") -> list[dict]:
    """
    Retrieve the top-k most relevant chunks using the specified strategy.
    
    Args:
        strategy: One of 'vector', 'keyword', 'hybrid'
    """
    if strategy == "keyword":
        return retrieve_bm25(query, top_k)
    elif strategy == "hybrid":
        return retrieve_hybrid(query, top_k)
    else:
        return retrieve_vector(query, top_k)


# ── Generation (Ollama) ─────────────────────────────────────────────────────
def condense_query(question: str, history: list) -> str:
    """
    Given a follow-up question and previous chat history, rewrite the question
    to be a standalone search query containing all necessary context.
    """
    if not history:
        return question
        
    chat_history_str = ""
    # Only take the last 6 messages to keep the context size reasonable
    for msg in history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        chat_history_str += f"{role}: {msg['content']}\n"
        
    condense_prompt = f"""Given the following conversation history and a follow-up question, rewrite the follow-up question to be a standalone, self-contained search query. 
The standalone query should contain all the necessary details and context from the conversation history (like specific income values, expenses, or sections mentioned) so it can be used for search.
Do NOT answer the question. Just output the standalone query and nothing else.

Conversation History:
{chat_history_str}
Follow-up Question: {question}

Standalone Query:"""

    import urllib.request
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": condense_prompt,
        "stream": False,
        "options": {"temperature": 0.0},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            standalone = body.get("response", "").strip()
            if standalone.startswith('"') and standalone.endswith('"'):
                standalone = standalone[1:-1].strip()
            print(f"Condensed query: '{question}' -> '{standalone}'")
            return standalone
    except Exception as e:
        print(f"Error condensing query: {e}")
        return question


def generate(query: str, chunks: list[dict], prompt_template: str, temperature: float = 0.0, history: list = None) -> str:
    """Generate an answer using Ollama (local LLM) with retrieved context and history."""
    import urllib.request

    context_items = []
    for c in chunks:
        context_items.append(f"Source: {c['source']}, Section: {c['section']} (Paragraph {c['paragraph_index'] + 1})\nContent: {c['text']}")
    context = "\n\n".join(context_items)
    
    # Format previous conversation transcript
    chat_history_str = ""
    if history:
        for msg in history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            chat_history_str += f"{role}: {msg['content']}\n"

    # Inject history into the prompt question placeholder
    if chat_history_str:
        question_with_history = f"Previous Conversation:\n{chat_history_str}\nFollow-up Question: {query}"
        prompt = prompt_template.replace("{context}", context).replace("{question}", question_with_history)
    else:
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


def verify_grounding(answer: str, context_chunks: list, question: str) -> tuple[bool, list]:
    """
    Checks if all numbers/percentages/monetary values in the LLM's answer
    exist in the retrieved context chunks or the user's question.
    
    Returns: (is_grounded, list_of_ungrounded_numbers)
    """
    # 1. Clean citations (e.g., [1], [Source: ...]) to avoid checking citation numbers
    clean_answer = re.sub(r'\[[^\]]*\]', ' ', answer)
    
    # 2. Extract number tokens: digits, commas, periods, optional %, lakh, cr, etc.
    tokens = re.findall(r'\b\d+(?:[,\.]\d+)*(?:\s*(?:lakh|%|lpa|cr))?\b', clean_answer.lower())
    
    # Combine all context text and user question into one normalized string
    context_texts = []
    for chunk in context_chunks:
        if isinstance(chunk, dict):
            context_texts.append(chunk.get("text", "").lower())
        else:
            context_texts.append(str(chunk).lower())
    context_str = " ".join(context_texts) + " " + question.lower()
    
    def check_presence(tok):
        if tok in context_str:
            return True
            
        tok_clean = tok.replace(",", "")
        if tok_clean in context_str:
            return True
            
        if "." in tok:
            try:
                val = float(tok.replace(" lakh", "").replace("%", ""))
                if val.is_integer() and str(int(val)) in context_str:
                    return True
            except ValueError:
                pass
                
        if "lakh" in tok:
            try:
                num_part = float(tok.split("lakh")[0].strip())
                val_int = int(num_part * 100000)
                val_formatted = f"{val_int:,}"
                if str(val_int) in context_str or val_formatted in context_str:
                    return True
            except ValueError:
                pass
                
        if "%" in tok:
            tok_num = tok.replace("%", "").strip()
            if tok_num in context_str:
                return True
                
        return False

    ungrounded = []
    for tok in tokens:
        # Ignore generic small numbers that are too common
        if tok.strip() in ["0", "1", "2", "3", "4", "5"]:
            continue
            
        if not check_presence(tok):
            ungrounded.append(tok)
            
    return (len(ungrounded) == 0, list(set(ungrounded)))


# ── High-level query ─────────────────────────────────────────────────────────
def query(question: str, config: dict = None, history: list = None) -> dict:
    """End-to-end RAG query: retrieve context then generate answer."""
    if config is None:
        config = load_config()

    # 1. Condense query if history exists to retrieve appropriate documents
    search_query = question
    if history:
        search_query = condense_query(question, history)

    strategy = config.get("retrieval_strategy", "vector")
    chunks = retrieve(search_query, top_k=int(config.get("top_k", 3)), strategy=strategy)
    answer = generate(
        query=question,
        chunks=chunks,
        prompt_template=config.get("prompt_template", "Context: {context}\n\nQuestion: {question}\n\nAnswer:"),
        temperature=float(config.get("temperature", 0.0)),
        history=history
    )
    
    grounding_passed, ungrounded_numbers = verify_grounding(answer, chunks, question)
    
    return {
        "question": question,
        "search_query_used": search_query,
        "answer": answer,
        "sources": chunks,
        "config_used": config,
        "grounding_passed": grounding_passed,
        "ungrounded_numbers": ungrounded_numbers,
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
