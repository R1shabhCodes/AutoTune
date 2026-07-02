# benchmark.py
# Runs the RAG pipeline with two configs (default vs optimized) and produces
# a side-by-side comparison table plus a bar chart.
# Usage: python benchmark.py

import os
import sys
import json
import time

# Ensure imports work from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rag_pipeline as rag

# ── Evaluation set (same questions AutoTune uses) ────────────────────────────
EVAL_SET = [
    {"question": "What is the tax rate for income above 15 lakh under the new regime?", "expected": ["30%"]},
    {"question": "What is the maximum deduction allowed under Section 80C?", "expected": ["1.5 lakh"]},
    {"question": "What is the standard deduction for salaried individuals under the new tax regime?", "expected": ["75,000"]},
    {"question": "What are the four types of GST in India?", "expected": ["CGST", "SGST", "IGST"]},
    {"question": "What is the GST rate for IT services?", "expected": ["18%"]},
    {"question": "When was GST introduced in India?", "expected": ["2017"]},
    {"question": "What is the lock-in period for ELSS mutual funds?", "expected": ["3 years"]},
    {"question": "What does NAV stand for in mutual funds?", "expected": ["Net Asset Value"]},
    {"question": "What is the minimum SIP amount in most mutual funds?", "expected": ["500"]},
    {"question": "What is the current repo rate set by RBI?", "expected": ["6.50"]},
    {"question": "What is the current CRR in India?", "expected": ["4.50"]},
    {"question": "What is the inflation target set by RBI?", "expected": ["4%"]},
    {"question": "What was the STCG tax rate on listed equity changed to in Budget 2024?", "expected": ["20%"]},
    {"question": "What is the LTCG exemption limit on listed equity after Budget 2024?", "expected": ["1.25 lakh"]},
    {"question": "What is the fiscal deficit target for FY 2024-25?", "expected": ["4.9%"]},
]


def evaluate(config: dict, label: str) -> dict:
    """Run all evaluation questions against a config and return results."""
    print(f"\n{'='*60}")
    print(f"  EVALUATING: {label}")
    print(f"  Config: chunk_size={config['chunk_size']}, overlap={config['chunk_overlap']}, top_k={config['top_k']}")
    print(f"{'='*60}\n")

    # Build index with this config
    rag.build_index(
        chunk_size=int(config["chunk_size"]),
        chunk_overlap=int(config["chunk_overlap"]),
    )

    results = []
    total_score = 0.0

    for idx, item in enumerate(EVAL_SET):
        question = item["question"]
        expected = item["expected"]

        result = rag.query(question, config)
        answer = result["answer"].lower()

        matched = sum(1 for term in expected if term.lower() in answer)
        score = matched / len(expected) if expected else 0.0
        total_score += score

        status = "✅" if score >= 0.5 else "❌"
        print(f"  [{idx+1:2d}/{len(EVAL_SET)}] {status} Score: {score:.2f} | {question}")
        if score < 1.0:
            print(f"           Expected: {expected}")
            print(f"           Answer:   {answer[:120]}...")

        results.append({
            "question": question,
            "expected": expected,
            "answer": result["answer"],
            "score": score,
        })

    aggregate = total_score / len(EVAL_SET) if EVAL_SET else 0.0
    print(f"\n  📊 {label} Aggregate Score: {aggregate:.4f} ({aggregate*100:.1f}%)\n")
    return {"label": label, "aggregate_score": aggregate, "results": results, "config": config}


def print_comparison(default_result: dict, optimized_result: dict):
    """Print a detailed side-by-side comparison."""
    print("\n" + "=" * 80)
    print("  📊 BENCHMARK COMPARISON: DEFAULT vs OPTIMIZED")
    print("=" * 80)

    # Config comparison
    print("\n  Configuration:")
    print(f"  {'Parameter':<20} {'Default':<20} {'Optimized':<20}")
    print(f"  {'-'*60}")
    for key in ["chunk_size", "chunk_overlap", "top_k", "temperature"]:
        dv = str(default_result["config"].get(key, "N/A"))
        ov = str(optimized_result["config"].get(key, "N/A"))
        marker = " ✨" if dv != ov else ""
        print(f"  {key:<20} {dv:<20} {ov:<20}{marker}")

    # Score comparison
    print(f"\n  {'Question':<65} {'Default':<10} {'Optimized':<10}")
    print(f"  {'-'*85}")
    for d, o in zip(default_result["results"], optimized_result["results"]):
        q = d["question"][:62] + "..." if len(d["question"]) > 62 else d["question"]
        ds = f"{d['score']:.2f}"
        os_ = f"{o['score']:.2f}"
        marker = " ⬆" if o["score"] > d["score"] else (" ⬇" if o["score"] < d["score"] else "  ")
        print(f"  {q:<65} {ds:<10} {os_:<10}{marker}")

    # Summary
    d_agg = default_result["aggregate_score"]
    o_agg = optimized_result["aggregate_score"]
    improvement = o_agg - d_agg
    pct_change = ((o_agg - d_agg) / d_agg * 100) if d_agg > 0 else 0

    print(f"\n  {'='*85}")
    print(f"  AGGREGATE SCORE:     Default = {d_agg:.4f} ({d_agg*100:.1f}%)    |    Optimized = {o_agg:.4f} ({o_agg*100:.1f}%)")
    print(f"  IMPROVEMENT:         +{improvement:.4f} ({pct_change:+.1f}% relative)")
    print(f"  {'='*85}\n")

    # Save results to JSON
    output = {
        "default": {"score": d_agg, "config": default_result["config"]},
        "optimized": {"score": o_agg, "config": optimized_result["config"]},
        "improvement": improvement,
        "improvement_pct": pct_change,
    }
    with open("benchmark_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print("  📁 Results saved to benchmark_results.json\n")


def main():
    print("\n" + "=" * 80)
    print("  🏦 RAG-Finance Benchmark: Before vs After AutoTune Optimization")
    print("=" * 80)

    # Default config (intentionally suboptimal)
    default_config = {
        "chunk_size": 200,
        "chunk_overlap": 20,
        "top_k": 2,
        "temperature": 0.0,
        "prompt_template": "Answer the following question based on the provided context. If the answer is not in the context, say 'I don't have enough information to answer this question.'\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:",
    }

    # Check if optimized config exists (produced by AutoTune)
    optimized_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_optimized.json")
    if os.path.exists(optimized_path):
        with open(optimized_path, "r") as f:
            optimized_config = json.load(f)
        print(f"\n  ✅ Found optimized config at: {optimized_path}")
    else:
        # If no optimized config, use current config.json (which may have been updated by AutoTune)
        current_config = rag.load_config()
        if current_config != default_config:
            optimized_config = current_config
            print(f"\n  ℹ️  Using current config.json as optimized config (differs from default)")
        else:
            print(f"\n  ⚠️  No optimized config found. Run AutoTune first to generate one!")
            print(f"     Creating a sample optimized config with better defaults for demo...\n")
            optimized_config = {
                "chunk_size": 500,
                "chunk_overlap": 50,
                "top_k": 5,
                "temperature": 0.0,
                "prompt_template": "You are a finance expert. Answer the question accurately and concisely using ONLY the provided context. Include specific numbers, rates, and percentages when available.\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:",
            }

    # Run evaluations
    start = time.time()
    default_result = evaluate(default_config, "DEFAULT (Before AutoTune)")
    optimized_result = evaluate(optimized_config, "OPTIMIZED (After AutoTune)")
    elapsed = time.time() - start

    # Print comparison
    print_comparison(default_result, optimized_result)
    print(f"  ⏱ Total benchmark time: {elapsed:.1f}s\n")


if __name__ == "__main__":
    main()
