# config.py
# Current configuration for AutoTune RAG pipeline
# This file is programmatically read and updated by agent_loop.py

CONFIG = {'chunk_size': 100, 'chunk_overlap': 50, 'top_k': 6, 'temperature': 0.0, 'retrieval_strategy': 'vector', 'prompt_template': 'Answer the question based ONLY on the context provided. If you do not know the answer, say you do not know.\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:'}
