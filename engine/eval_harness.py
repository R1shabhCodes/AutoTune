# eval_harness.py
# Loads eval_set.json, runs the RAG pipeline with a given config, and computes evaluation score.
# This file is fixed and is NOT modified by the optimization agent.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import time
import rag_pipeline

def evaluate_dataset(config: dict, filename: str) -> dict:
    """Helper to evaluate a config against a specific JSON file in engine dir."""
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    eval_path = os.path.join(engine_dir, filename)
    if not os.path.exists(eval_path):
        raise FileNotFoundError(f"Evaluation set file not found: {eval_path}")
        
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)
        
    # 2. Re-build index with new chunking settings
    print(f"Re-indexing with chunk_size={config['chunk_size']}, chunk_overlap={config['chunk_overlap']}...")
    rag_pipeline.build_index(
        chunk_size=int(config["chunk_size"]),
        chunk_overlap=int(config["chunk_overlap"])
    )
    
    results = []
    total_score = 0.0
    total_latency_ms = 0.0
    total_retrieval_ms = 0.0
    total_generation_ms = 0.0
    total_tokens = 0
    
    retrieval_strategy = config.get("retrieval_strategy", "vector")
    
    # 3. Evaluate each question
    print(f"Evaluating {len(eval_set)} questions from {filename}...")
    for idx, item in enumerate(eval_set):
        question = item["question"]
        expected_list = item["expected_answer_contains"]
        
        # Rate limit sleep only if using Gemini API
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
        
        # Retrieve context (with timing)
        t_ret_start = time.time()
        chunks = rag_pipeline.retrieve(question, top_k=int(config["top_k"]), strategy=retrieval_strategy)
        t_ret_end = time.time()
        retrieval_ms = (t_ret_end - t_ret_start) * 1000
        
        # Generate response (with timing)
        t_gen_start = time.time()
        generated_answer = rag_pipeline.generate(
            query=question,
            chunks=chunks,
            prompt_template=config["prompt_template"],
            temperature=float(config["temperature"])
        )
        t_gen_end = time.time()
        generation_ms = (t_gen_end - t_gen_start) * 1000
        
        question_latency_ms = retrieval_ms + generation_ms
        
        # Approximate token count (prompt + answer chars / 4)
        prompt_text = config["prompt_template"].replace("{context}", "\n\n".join(chunks) if chunks else "").replace("{question}", question)
        question_tokens = (len(prompt_text) + len(generated_answer)) // 4
        
        total_latency_ms += question_latency_ms
        total_retrieval_ms += retrieval_ms
        total_generation_ms += generation_ms
        total_tokens += question_tokens
        
        # Score response based on keyword overlap (substring matching)
        matched_count = 0
        answer_lower = generated_answer.lower()
        
        for term in expected_list:
            if term.lower() in answer_lower:
                matched_count += 1
                
        question_score = (matched_count / len(expected_list)) if expected_list else 0.0
        total_score += question_score
        
        citation_present = "[source:" in answer_lower
        
        # Run heuristic grounding check
        grounding_passed, ungrounded_numbers = rag_pipeline.verify_grounding(generated_answer, chunks, question)
        print(f"[{idx+1}/{len(eval_set)}] Score: {question_score:.2f} | Citation: {citation_present} | Grounded: {grounding_passed} | Question: {question}")
        
        results.append({
            "question": question,
            "expected_terms": expected_list,
            "expected": expected_list,
            "generated_answer": generated_answer,
            "actual_answer": generated_answer,
            "score": question_score,
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
    aggregate_score = (total_score / num_questions)
    avg_latency_ms = total_latency_ms / num_questions
    avg_retrieval_ms = total_retrieval_ms / num_questions
    avg_generation_ms = total_generation_ms / num_questions
    
    grounding_passed_count = sum(1 for r in results if r["grounding_passed"])
    grounding_rate = grounding_passed_count / num_questions
    
    print(f"Evaluation Complete ({filename}). Aggregate Score: {aggregate_score:.4f} | Avg Latency: {avg_latency_ms:.0f}ms | Grounding: {grounding_rate*100:.1f}%")
    
    return {
        "aggregate_score": aggregate_score,
        "avg_latency_ms": round(avg_latency_ms, 1),
        "avg_retrieval_ms": round(avg_retrieval_ms, 1),
        "avg_generation_ms": round(avg_generation_ms, 1),
        "total_tokens": total_tokens,
        "grounding_rate": round(grounding_rate, 4),
        "results": results
    }

def evaluate_config(config: dict) -> dict:
    """Evaluates a RAG configuration against the tuning evaluation set."""
    return evaluate_dataset(config, "eval_set_tuning.json")

def evaluate_holdout(config: dict) -> dict:
    """Evaluates a RAG configuration against the holdout evaluation set (never used during tuning)."""
    return evaluate_dataset(config, "eval_set_holdout.json")

if __name__ == "__main__":
    # Test evaluation harness using current config.py settings
    import sys
    try:
        from config import CONFIG
        print("Testing evaluation harness with current config...")
        res = evaluate_config(CONFIG)
        print(f"\nFinal Test Score: {res['aggregate_score']:.4f}")
        print(f"Avg Latency: {res['avg_latency_ms']:.1f}ms")
        print(f"Total Tokens: {res['total_tokens']}")
    except Exception as e:
        print(f"Error running test evaluation: {e}", file=sys.stderr)
