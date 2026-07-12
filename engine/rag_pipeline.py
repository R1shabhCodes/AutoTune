# rag_pipeline.py
# Pure functions for indexing, retrieval, and generation.
# This file is fixed and is NOT modified by the optimization agent.

import os
import re
import glob
import json
import urllib.request
import urllib.error
import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

# Cache embedding model to avoid reloading on every function call
_embedding_model = None

# BM25 index globals (rebuilt on each build_index call)
_bm25_index = None
_bm25_corpus_chunks = []   # list of chunk text strings
_bm25_tokenized = []       # tokenized version for BM25

def get_embedding_model():
    """Singleton to load and cache the local sentence-transformer model."""
    global _embedding_model
    if _embedding_model is None:
        print("Loading local sentence-transformer model ('all-MiniLM-L6-v2')...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def _tokenize(text: str) -> list:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r'\w+', text.lower())

def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list:
    """Splits a document text into overlapping character-level chunks."""
    if chunk_size <= 0:
        return [text]
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        
        # Calculate next start position based on overlap
        step = chunk_size - chunk_overlap
        if step <= 0:
            # Prevent infinite loops if overlap >= chunk_size
            step = 1
        start += step
        
        # Avoid creating tiny trailing chunks
        if start >= text_len:
            break
            
    return chunks

def build_index(chunk_size: int, chunk_overlap: int):
    """
    Reads all text files in the corpus directory, chunks them,
    computes embeddings, stores them in ChromaDB, and builds BM25 index.
    """
    global _bm25_index, _bm25_corpus_chunks, _bm25_tokenized
    
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    corpus_dir = os.path.join(engine_dir, "corpus")
    if not os.path.exists(corpus_dir):
        os.makedirs(corpus_dir)
        
    text_files = glob.glob(os.path.join(corpus_dir, "*.txt"))
    if not text_files:
        raise ValueError(f"No text files found in the corpus directory: {corpus_dir}")
        
    chunks = []
    for filepath in text_files:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        file_chunks = chunk_text(content, chunk_size, chunk_overlap)
        for idx, chunk_content in enumerate(file_chunks):
            chunks.append({
                "text": chunk_content,
                "source": filename,
                "index": idx
            })
            
    if not chunks:
        raise ValueError("No chunks were generated from the corpus files.")
        
    # Generate embeddings
    model = get_embedding_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    
    # Setup persistent ChromaDB client
    chroma_path = os.path.join(engine_dir, "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)
    
    collection = client.get_or_create_collection("autotune_rag")
    
    # Clean old documents in a single atomic step to avoid stale cached UUIDs
    try:
        existing = collection.get()
        if existing and "ids" in existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception as e:
        print(f"Warning clearing collection: {e}")
    
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source": c["source"], "index": c["index"]} for c in chunks]
    
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas
    )
    
    # Build BM25 index from the same chunks
    _bm25_corpus_chunks = texts
    _bm25_tokenized = [_tokenize(t) for t in texts]
    if _bm25_tokenized:
        _bm25_index = BM25Okapi(_bm25_tokenized)
    else:
        _bm25_index = None
    
    print(f"Index built successfully. Indexed {len(chunks)} chunks from {len(text_files)} files.")

def retrieve_vector(query: str, top_k: int) -> list:
    """Retrieves the top_k most relevant chunks using vector similarity (ChromaDB)."""
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    chroma_path = os.path.join(engine_dir, "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)
    try:
        collection = client.get_collection("autotune_rag")
    except Exception:
        print("Warning: ChromaDB collection 'autotune_rag' does not exist. Run build_index first.")
        return []
        
    model = get_embedding_model()
    query_embedding = model.encode([query], show_progress_bar=False)[0].tolist()
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    if results and "documents" in results and results["documents"]:
        return results["documents"][0]
    return []

def retrieve_bm25(query: str, top_k: int) -> list:
    """Retrieves the top_k most relevant chunks using BM25 keyword matching."""
    global _bm25_index, _bm25_corpus_chunks
    
    if _bm25_index is None or not _bm25_corpus_chunks:
        return []
    
    tokenized_query = _tokenize(query)
    scores = _bm25_index.get_scores(tokenized_query)
    
    # Get top-k indices sorted by score descending
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    
    return [_bm25_corpus_chunks[i] for i in top_indices if scores[i] > 0]

def retrieve_hybrid(query: str, top_k: int) -> list:
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
    
    # Compute RRF scores
    rrf_scores = {}
    
    for rank, doc in enumerate(vector_results):
        doc_key = doc[:200]  # Use prefix as dedup key
        rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + 1.0 / (RRF_K + rank + 1)
    
    for rank, doc in enumerate(bm25_results):
        doc_key = doc[:200]
        rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + 1.0 / (RRF_K + rank + 1)
    
    # Build a map from key -> full doc text
    doc_map = {}
    for doc in vector_results + bm25_results:
        doc_key = doc[:200]
        if doc_key not in doc_map:
            doc_map[doc_key] = doc
    
    # Sort by RRF score and return top_k
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)[:top_k]
    
    return [doc_map[k] for k in sorted_keys]

def retrieve(query: str, top_k: int, strategy: str = "vector") -> list:
    """
    Retrieves the top_k most relevant chunks using the specified strategy.
    
    Args:
        strategy: One of 'vector', 'keyword', 'hybrid'
    """
    if strategy == "keyword":
        return retrieve_bm25(query, top_k)
    elif strategy == "hybrid":
        return retrieve_hybrid(query, top_k)
    else:
        return retrieve_vector(query, top_k)

def call_llm(prompt: str, temperature: float, system_prompt: str = None) -> str:
    """
    Routes the LLM request to the Gemini API (if key is present)
    or falls back to the local Ollama instance.
    """
    # Look for API key in environment or .env file
    gemini_key = os.environ.get("GEMINI_API_KEY")
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(engine_dir, ".env")
    if not gemini_key and os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    if k.strip() == "GEMINI_API_KEY":
                        gemini_key = v.strip().strip('"').strip("'")
                        break
                        
    if gemini_key:
        # Cloud LLM: Gemini API
        model = "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        
        contents = {"parts": [{"text": prompt}]}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
            
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                resp = json.loads(res.read().decode("utf-8"))
                return resp["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"Error calling Gemini API: {str(e)}"
    else:
        # Local LLM: Ollama
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        url = f"{ollama_url}/api/generate"
        model = "qwen2.5:1.5b"
        
        # Combine system prompt with main prompt for Ollama since API is /api/generate
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"System Instruction: {system_prompt}\n\nUser Question:\n{prompt}"
            
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                resp = json.loads(res.read().decode("utf-8"))
                return resp.get("response", "")
        except Exception as e:
            return f"Error calling local Ollama (is it running and does it have model 'llama3.2'?): {str(e)}"

def generate(query: str, chunks: list, prompt_template: str, temperature: float, history: list = None) -> str:
    """Formats the prompt with retrieved chunks (context) and calls the active LLM."""
    context = "\n\n".join(chunks) if chunks else "No context retrieved."
    prompt = prompt_template.replace("{context}", context).replace("{question}", query)
    return call_llm(prompt, temperature)

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
