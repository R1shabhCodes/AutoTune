# eval_harness.py
# Loads evaluation datasets, executes the RAG pipeline with experimental isolation,
# and computes accuracy, latency, tokens, and grounding metrics.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import time
from typing import Dict, Any, Optional
import rag_pipeline

def evaluate_dataset(config: Dict[str, Any], filename: str, is_experimental: bool = True) -> Dict[str, Any]:
    """
    Evaluates a configuration against a specific JSON dataset file.
    Reuses cached index when chunk parameters are unchanged and protects production index.
    """
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    eval_path = os.path.join(engine_dir, filename)
    if not os.path.exists(eval_path):
        raise FileNotFoundError(f"Evaluation set file not found: {eval_path}")

    with open(eval_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    chunk_size = int(config["chunk_size"])
    chunk_overlap = int(config["chunk_overlap"])

    # Ensure index exists in cache/isolated namespace
    collection_name = rag_pipeline.build_index(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        is_experimental=is_experimental
    )

    corpus_dir = os.path.join(engine_dir, "corpus")
    cache_key = rag_pipeline.get_index_cache_key(chunk_size, chunk_overlap, corpus_dir)

    results = []
    total_score = 0.0
    total_latency_ms = 0.0
    total_retrieval_ms = 0.0
    total_generation_ms = 0.0
    total_tokens = 0

    retrieval_strategy = config.get("retrieval_strategy", "vector")

    # Evaluate each question
    print(f"Evaluating {len(eval_set)} questions from {filename} using namespace '{collection_name}'...")
    for idx, item in enumerate(eval_set):
        question = item["question"]
        expected_list = item.get("expected_answer_contains", item.get("expected", []))

        # Rate limit only if using Gemini API
        gemini_key = os.environ.get("GEMINI_API_KEY")
        env_path = os.path.join(engine_dir, ".env")
        if not gemini_key and os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        if k.strip() == "GEMINI_API_KEY" and v.strip():
                            gemini_key = v.strip().strip('"').strip("'")
                            break
        if gemini_key and idx > 0:
            time.sleep(4.0)

        # 1. Retrieve context with timing
        t_ret_start = time.time()
        chunks = rag_pipeline.retrieve(
            question,
            top_k=int(config["top_k"]),
            strategy=retrieval_strategy,
            collection_name=collection_name,
            cache_key=cache_key
        )
        t_ret_end = time.time()
        retrieval_ms = (t_ret_end - t_ret_start) * 1000

        # 2. Generate response with timing
        t_gen_start = time.time()
        generated_answer = rag_pipeline.generate(
            query=question,
            chunks=chunks,
            prompt_template=config.get("prompt_template", "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"),
            temperature=float(config.get("temperature", 0.0))
        )
        t_gen_end = time.time()
        generation_ms = (t_gen_end - t_gen_start) * 1000

        question_latency_ms = retrieval_ms + generation_ms

        # Approximate token count
        prompt_tmpl = config.get("prompt_template", "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:")
        prompt_text = prompt_tmpl.replace("{context}", "\n\n".join(chunks) if chunks else "").replace("{question}", question)
        question_tokens = (len(prompt_text) + len(generated_answer)) // 4

        total_latency_ms += question_latency_ms
        total_retrieval_ms += retrieval_ms
        total_generation_ms += generation_ms
        total_tokens += question_tokens

        # Score response based on expected term presence
        matched_count = 0
        answer_lower = generated_answer.lower()

        for term in expected_list:
            if term.lower() in answer_lower:
                matched_count += 1

        question_score = (matched_count / len(expected_list)) if expected_list else 0.0
        total_score += question_score

        citation_present = "[source:" in answer_lower or "[source" in answer_lower

        # Run heuristic grounding check
        grounding_passed, ungrounded_numbers = rag_pipeline.verify_grounding(generated_answer, chunks, question)

        results.append({
            "question": question,
            "expected_terms": expected_list,
            "expected": expected_list,
            "generated_answer": generated_answer,
            "actual_answer": generated_answer,
            "score": round(question_score, 4),
            "passed": bool(question_score >= 1.0),
            "citation_present": citation_present,
            "latency_ms": round(question_latency_ms, 1),
            "retrieval_ms": round(retrieval_ms, 1),
            "generation_ms": round(generation_ms, 1),
            "tokens": question_tokens,
            "grounding_passed": grounding_passed,
            "ungrounded_numbers": ungrounded_numbers,
        })

    num_questions = len(eval_set) if eval_set else 1
    aggregate_score = round(total_score / num_questions, 4)
    avg_latency_ms = round(total_latency_ms / num_questions, 1)
    avg_retrieval_ms = round(total_retrieval_ms / num_questions, 1)
    avg_generation_ms = round(total_generation_ms / num_questions, 1)

    grounding_passed_count = sum(1 for r in results if r["grounding_passed"])
    grounding_rate = round(grounding_passed_count / num_questions, 4)

    return {
        "aggregate_score": aggregate_score,
        "avg_latency_ms": avg_latency_ms,
        "avg_retrieval_ms": avg_retrieval_ms,
        "avg_generation_ms": avg_generation_ms,
        "total_tokens": total_tokens,
        "grounding_rate": grounding_rate,
        "results": results
    }

def evaluate_config(config: Dict[str, Any], is_experimental: bool = True) -> Dict[str, Any]:
    """Evaluates a RAG configuration against the tuning evaluation set."""
    return evaluate_dataset(config, "eval_set_tuning.json", is_experimental=is_experimental)

def evaluate_holdout(config: Dict[str, Any], is_experimental: bool = False) -> Dict[str, Any]:
    """Evaluates a RAG configuration against the holdout evaluation set."""
    return evaluate_dataset(config, "eval_set_holdout.json", is_experimental=is_experimental)

if __name__ == "__main__":
    from config import CONFIG
    print("Testing evaluation harness with active configuration...")
    res = evaluate_config(CONFIG, is_experimental=True)
    print(f"Test Score: {res['aggregate_score']} | Latency: {res['avg_latency_ms']}ms | Grounding: {res['grounding_rate']}")
