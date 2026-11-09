# rag_pipeline.py
# Pure functions for indexing, retrieval, and generation.
# Enhanced in AutoTune 2.0 with corpus fingerprinting, index caching,
# and safe experimental namespaces to protect production indices.

import os
import re
import glob
import json
import hashlib
import urllib.request
import urllib.error
from typing import Optional, Tuple, List, Dict
from rank_bm25 import BM25Okapi

# Cache embedding model to avoid reloading on every function call
_embedding_model = None

# In-memory BM25 index cache: cache_key -> (BM25Okapi, list of texts, list of tokenized texts)
_bm25_cache: Dict[str, Tuple[Optional[BM25Okapi], List[str], List[List[str]]]] = {}

# Active BM25 index globals (for backward compatibility)
_bm25_index = None
_bm25_corpus_chunks = []
_bm25_tokenized = []

def get_embedding_model():
    """Singleton to load and cache the local sentence-transformer model."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
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
            step = 1
        start += step
        
        if start >= text_len:
            break
            
    return chunks

def get_corpus_fingerprint(corpus_dir: Optional[str] = None) -> str:
    """
    Computes a deterministic SHA256 fingerprint across all text files in the corpus directory.
    Guarantees index rebuilds trigger if document content changes.
    """
    if corpus_dir is None:
        engine_dir = os.path.dirname(os.path.abspath(__file__))
        corpus_dir = os.path.join(engine_dir, "corpus")

    if not os.path.exists(corpus_dir):
        return "empty_corpus"

    text_files = sorted(glob.glob(os.path.join(corpus_dir, "*.txt")))
    if not text_files:
        return "no_text_files"

    hasher = hashlib.sha256()
    for fpath in text_files:
        fname = os.path.basename(fpath)
        hasher.update(fname.encode("utf-8"))
        with open(fpath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)

    return hasher.hexdigest()

def get_index_cache_key(chunk_size: int, chunk_overlap: int, corpus_dir: Optional[str] = None) -> str:
    """
    Returns a unique identifier for an index configuration.
    """
    fp = get_corpus_fingerprint(corpus_dir)
    return f"idx_{fp[:8]}_cs{chunk_size}_co{chunk_overlap}"

def build_index(
    chunk_size: int,
    chunk_overlap: int,
    collection_name: Optional[str] = None,
    is_experimental: bool = False,
    force_rebuild: bool = False
) -> str:
    """
    Indexes the corpus into ChromaDB and builds the BM25 index.
    
    When is_experimental=True:
      - Uses an isolated cache namespace.
      - If the index for this (corpus_fingerprint, chunk_size, chunk_overlap) already exists,
        it reuses the cached index immediately without redundant re-embedding.
      - NEVER touches or modifies the production index ('autotune_rag').
    """
    global _bm25_index, _bm25_corpus_chunks, _bm25_tokenized, _bm25_cache

    engine_dir = os.path.dirname(os.path.abspath(__file__))
    corpus_dir = os.path.join(engine_dir, "corpus")
    if not os.path.exists(corpus_dir):
        os.makedirs(corpus_dir)

    cache_key = get_index_cache_key(chunk_size, chunk_overlap, corpus_dir)

    if collection_name is None:
        collection_name = cache_key if is_experimental else "autotune_rag"

    # Setup persistent ChromaDB client
    import chromadb
    chroma_path = os.path.join(engine_dir, "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)

    # 1. Check if cached index exists in Chroma and BM25 cache
    if not force_rebuild:
        try:
            coll = client.get_collection(collection_name)
            doc_count = coll.count()
            if doc_count > 0 and cache_key in _bm25_cache:
                print(f"Reusing cached index '{collection_name}' ({doc_count} chunks). Skipping re-embedding.")
                _bm25_index, _bm25_corpus_chunks, _bm25_tokenized = _bm25_cache[cache_key]
                return collection_name
        except Exception:
            pass

    # 2. Build index from corpus
    text_files = sorted(glob.glob(os.path.join(corpus_dir, "*.txt")))
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

    collection = client.get_or_create_collection(collection_name)

    # Clear old documents from this specific collection if rebuilding
    try:
        existing = collection.get()
        if existing and "ids" in existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception as e:
        print(f"Warning clearing collection '{collection_name}': {e}")

    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source": c["source"], "index": c["index"]} for c in chunks]

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas
    )

    # Build and cache BM25 index
    tokenized = [_tokenize(t) for t in texts]
    bm25 = BM25Okapi(tokenized) if tokenized else None

    _bm25_cache[cache_key] = (bm25, texts, tokenized)
    _bm25_index = bm25
    _bm25_corpus_chunks = texts
    _bm25_tokenized = tokenized

    print(f"Index built successfully in namespace '{collection_name}'. Indexed {len(chunks)} chunks from {len(text_files)} files.")
    return collection_name

def promote_index_to_production(chunk_size: int, chunk_overlap: int):
    """
    Promotes an accepted index configuration into the production collection ('autotune_rag').
    """
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    corpus_dir = os.path.join(engine_dir, "corpus")
    cache_key = get_index_cache_key(chunk_size, chunk_overlap, corpus_dir)

    import chromadb
    chroma_path = os.path.join(engine_dir, "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)

    try:
        source_coll = client.get_collection(cache_key)
        data = source_coll.get(include=["documents", "embeddings", "metadatas"])
        
        prod_coll = client.get_or_create_collection("autotune_rag")
        existing = prod_coll.get()
        if existing and "ids" in existing and existing["ids"]:
            prod_coll.delete(ids=existing["ids"])
            
        if data and data.get("ids"):
            prod_coll.add(
                ids=data["ids"],
                documents=data["documents"],
                embeddings=data["embeddings"],
                metadatas=data["metadatas"]
            )
        print(f"Promoted index '{cache_key}' to production ('autotune_rag').")
    except Exception as e:
        print(f"Warning: Could not promote index '{cache_key}' directly, falling back to build_index: {e}")
        build_index(chunk_size, chunk_overlap, collection_name="autotune_rag", is_experimental=False)

def cleanup_experimental_indices(keep_cache_keys: Optional[List[str]] = None, max_keep: int = 10):
    """
    Safely prunes old experimental collections in ChromaDB, never touching 'autotune_rag'.
    """
    if keep_cache_keys is None:
        keep_cache_keys = []

    engine_dir = os.path.dirname(os.path.abspath(__file__))
    import chromadb
    chroma_path = os.path.join(engine_dir, "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)

    collections = client.list_collections()
    exp_colls = [c for c in collections if c.name.startswith("idx_")]

    if len(exp_colls) > max_keep:
        to_delete = exp_colls[:-max_keep]
        for c in to_delete:
            if c.name not in keep_cache_keys:
                try:
                    client.delete_collection(c.name)
                    print(f"Cleaned up experimental collection '{c.name}'")
                except Exception:
                    pass

def retrieve_vector(query: str, top_k: int, collection_name: str = "autotune_rag") -> list:
    """Retrieves the top_k most relevant chunks using vector similarity (ChromaDB)."""
    import chromadb
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    chroma_path = os.path.join(engine_dir, "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        # Fallback to autotune_rag if experimental collection is missing
        try:
            collection = client.get_collection("autotune_rag")
        except Exception:
            print(f"Warning: ChromaDB collection '{collection_name}' does not exist.")
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

def retrieve_bm25(query: str, top_k: int, cache_key: Optional[str] = None) -> list:
    """Retrieves the top_k most relevant chunks using BM25 keyword matching."""
    global _bm25_index, _bm25_corpus_chunks, _bm25_cache

    bm25_idx = _bm25_index
    corpus_chunks = _bm25_corpus_chunks

    if cache_key and cache_key in _bm25_cache:
        bm25_idx, corpus_chunks, _ = _bm25_cache[cache_key]

    if bm25_idx is None or not corpus_chunks:
        return []

    tokenized_query = _tokenize(query)
    scores = bm25_idx.get_scores(tokenized_query)

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [corpus_chunks[i] for i in top_indices if scores[i] > 0]

def retrieve_hybrid(query: str, top_k: int, collection_name: str = "autotune_rag", cache_key: Optional[str] = None) -> list:
    """
    Hybrid retrieval using Reciprocal Rank Fusion (RRF).
    Runs both vector search and BM25, fuses results using RRF formula.
    """
    RRF_K = 60
    fetch_k = min(top_k * 2, 20)

    vector_results = retrieve_vector(query, fetch_k, collection_name=collection_name)
    bm25_results = retrieve_bm25(query, fetch_k, cache_key=cache_key)

    rrf_scores = {}
    for rank, doc in enumerate(vector_results):
        doc_key = doc[:200]
        rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + 1.0 / (RRF_K + rank + 1)

    for rank, doc in enumerate(bm25_results):
        doc_key = doc[:200]
        rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + 1.0 / (RRF_K + rank + 1)

    doc_map = {}
    for doc in vector_results + bm25_results:
        doc_key = doc[:200]
        if doc_key not in doc_map:
            doc_map[doc_key] = doc

    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)[:top_k]
    return [doc_map[k] for k in sorted_keys]

def retrieve(query: str, top_k: int, strategy: str = "vector", collection_name: str = "autotune_rag", cache_key: Optional[str] = None) -> list:
    """
    Retrieves the top_k most relevant chunks using the specified strategy.
    Supports targeting experimental namespaces without affecting production.
    """
    if strategy == "keyword":
        return retrieve_bm25(query, top_k, cache_key=cache_key)
    elif strategy == "hybrid":
        return retrieve_hybrid(query, top_k, collection_name=collection_name, cache_key=cache_key)
    else:
        return retrieve_vector(query, top_k, collection_name=collection_name)

def call_llm(prompt: str, temperature: float, system_prompt: str = None, return_metadata: bool = False, model_override: Optional[str] = None):
    """
    Routes the LLM request to the configured generator model.
    Defaults to llama3.2:latest via Ollama, or Gemini API if GEMINI_API_KEY is present.
    Supports model_override to target alternative models (e.g. glm-5.2:cloud).
    """
    import models as model_provider

    gemini_key = model_provider.get_env_variable("GEMINI_API_KEY")

    if gemini_key:
        provider = "gemini"
        model = model_override or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
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
                text = resp["candidates"][0]["content"]["parts"][0]["text"]
                if return_metadata:
                    return text, False, None
                return text
        except Exception as e:
            cat = "auth_error" if "401" in str(e) or "403" in str(e) else "api_error"
            err_info = {
                "provider": provider,
                "model": model,
                "category": cat,
                "exception_type": type(e).__name__,
                "message": str(e)
            }
            err_msg = f"Error calling Gemini API: {str(e)}"
            if return_metadata:
                return err_msg, True, err_info
            return err_msg
    else:
        provider = "ollama"
        ollama_url = model_provider.get_ollama_base_url()
        url = f"{ollama_url}/api/generate"
        model = model_override or model_provider.get_generator_model()

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
            with urllib.request.urlopen(req, timeout=120) as res:
                resp = json.loads(res.read().decode("utf-8"))
                text = resp.get("response", "")
                if return_metadata:
                    return text, False, None
                return text
        except Exception as e:
            cat = "connection_refused" if "10061" in str(e) or "refused" in str(e).lower() else "timeout" if "timeout" in str(e).lower() else "runtime_error"
            err_info = {
                "provider": provider,
                "model": model,
                "category": cat,
                "exception_type": type(e).__name__,
                "message": f"Cannot connect to Ollama at {ollama_url}: {str(e)}" if cat == "connection_refused" else str(e)
            }
            err_msg = f"Error calling local Ollama (is it running and does it have model '{model}'?): {str(e)}"
            if return_metadata:
                return err_msg, True, err_info
            return err_msg

def generate(query: str, chunks: list, prompt_template: str, temperature: float, history: list = None, return_metadata: bool = False, model_override: Optional[str] = None):
    """Formats the prompt with retrieved chunks (context) and calls the active generator LLM (default: llama3.2:latest)."""
    context = "\n\n".join(chunks) if chunks else "No context retrieved."
    prompt = prompt_template.replace("{context}", context).replace("{question}", query)
    return call_llm(prompt, temperature, return_metadata=return_metadata, model_override=model_override)

def verify_grounding(answer: str, context_chunks: list, question: str) -> tuple[bool, list]:
    """
    Checks if all numbers/percentages/monetary values in the LLM's answer
    exist in the retrieved context chunks or the user's question.
    Returns: (is_grounded, list_of_ungrounded_numbers)
    """
    clean_answer = re.sub(r'\[[^\]]*\]', ' ', answer)
    tokens = re.findall(r'\b\d+(?:[,\.]\d+)*(?:\s*(?:lakh|%|lpa|cr))?\b', clean_answer.lower())

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
        if tok.strip() in ["0", "1", "2", "3", "4", "5"]:
            continue

        if not check_presence(tok):
            ungrounded.append(tok)

    return (len(ungrounded) == 0, list(set(ungrounded)))
