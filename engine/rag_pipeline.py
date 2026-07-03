# rag_pipeline.py
# Pure functions for indexing, retrieval, and generation.
# This file is fixed and is NOT modified by the optimization agent.

import os
import glob
import json
import urllib.request
import urllib.error
import chromadb
from sentence_transformers import SentenceTransformer

# Cache embedding model to avoid reloading on every function call
_embedding_model = None

def get_embedding_model():
    """Singleton to load and cache the local sentence-transformer model."""
    global _embedding_model
    if _embedding_model is None:
        print("Loading local sentence-transformer model ('all-MiniLM-L6-v2')...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

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
    computes embeddings, and stores them in a local ChromaDB collection.
    """
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
    print(f"Index built successfully. Indexed {len(chunks)} chunks from {len(text_files)} files.")

def retrieve(query: str, top_k: int) -> list:
    """Retrieves the top_k most relevant chunks from the ChromaDB index."""
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    chroma_path = os.path.join(engine_dir, "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)
    try:
        collection = client.get_collection("autotune_rag")
    except Exception:
        # If collection doesn't exist, return empty context
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
        url = "http://localhost:11434/api/generate"
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

def generate(query: str, chunks: list, prompt_template: str, temperature: float) -> str:
    """Formats the prompt with retrieved chunks (context) and calls the active LLM."""
    context = "\n\n".join(chunks) if chunks else "No context retrieved."
    prompt = prompt_template.replace("{context}", context).replace("{question}", query)
    return call_llm(prompt, temperature)
