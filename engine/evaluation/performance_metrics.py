"""
engine/evaluation/performance_metrics.py
Calculates latency percentiles (P50, P95), averages, token consumption, and error rates.
"""
from typing import List, Dict, Any


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculates nearest-rank or interpolated percentile."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (percentile / 100.0)
    f = int(k)
    c = f + 1
    if c < len(sorted_vals):
        d0 = sorted_vals[f] * (c - k)
        d1 = sorted_vals[c] * (k - f)
        return round(d0 + d1, 1)
    else:
        return round(sorted_vals[f], 1)


def compute_performance_metrics(samples: List[Any]) -> Dict[str, Any]:
    """
    Computes comprehensive latency and token metrics across a list of evaluation samples or results.
    """
    if not samples:
        return {
            "avg_latency_ms": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "avg_retrieval_ms": 0.0,
            "avg_generation_ms": 0.0,
            "avg_tokens_per_query": 0.0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "error_count": 0,
            "error_rate": 0.0
        }

    total_count = len(samples)
    latencies = [getattr(s, "latency_ms", 0.0) for s in samples]
    retrievals = [getattr(s, "retrieval_ms", 0.0) for s in samples]
    generations = [getattr(s, "generation_ms", 0.0) for s in samples]
    tokens = [getattr(s, "tokens", 0) for s in samples]
    costs = [getattr(s, "cost", 0.0) for s in samples]
    errors = sum(1 for s in samples if getattr(s, "is_error", False))

    avg_lat = sum(latencies) / total_count
    p50_lat = calculate_percentile(latencies, 50.0)
    p95_lat = calculate_percentile(latencies, 95.0)

    avg_ret = sum(retrievals) / total_count
    avg_gen = sum(generations) / total_count
    total_tok = sum(tokens)
    avg_tok = total_tok / total_count
    total_cost = sum(costs)

    return {
        "avg_latency_ms": round(avg_lat, 1),
        "p50_latency_ms": round(p50_lat, 1),
        "p95_latency_ms": round(p95_lat, 1),
        "avg_retrieval_ms": round(avg_ret, 1),
        "avg_generation_ms": round(avg_gen, 1),
        "avg_tokens_per_query": round(avg_tok, 1),
        "total_tokens": int(total_tok),
        "total_cost": round(total_cost, 6),
        "error_count": errors,
        "error_rate": round(errors / total_count, 4)
    }

