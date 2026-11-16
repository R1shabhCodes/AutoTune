# eval_harness.py
# AutoTune 2.0 Evaluation Harness
# Integrates modular EvaluationService with deterministic metrics, performance percentiles,
# grounding verification, and failure categorization, while preserving full backward compatibility.
#
# Memory optimization: evaluation package is imported lazily to avoid pulling in
# the full evaluation framework (and its transitive dependencies) at startup.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, Any, Optional


_service_instance: Optional[object] = None

def get_evaluation_service():
    """Lazily creates and caches the EvaluationService singleton."""
    global _service_instance
    if _service_instance is None:
        from evaluation import EvaluationService
        _service_instance = EvaluationService(run_semantic_judge=False)
    return _service_instance


def evaluate_dataset(
    config: Dict[str, Any],
    filename: str,
    role: str = "tuning",
    is_experimental: bool = True,
    adapter: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Evaluates a configuration against a specific JSON dataset file.
    Reuses cached index when chunk parameters are unchanged and protects production index.
    Returns legacy-compatible evaluation dictionary.
    """
    service = get_evaluation_service()
    report = service.evaluate_configuration(
        config=config,
        dataset_filename=filename,
        role=role,
        is_experimental=is_experimental,
        adapter=adapter
    )
    return service.to_legacy_eval_dict(report)


def evaluate_config(
    config: Dict[str, Any],
    is_experimental: bool = True,
    adapter: Optional[Any] = None
) -> Dict[str, Any]:
    """Evaluates a RAG configuration against the tuning evaluation set."""
    return evaluate_dataset(config, "eval_set_tuning.json", role="tuning", is_experimental=is_experimental, adapter=adapter)


def evaluate_holdout(
    config: Dict[str, Any],
    is_experimental: bool = False,
    adapter: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Evaluates a RAG configuration against the blind holdout evaluation set.
    Holdout questions remain strictly isolated from optimization prompts.
    """
    return evaluate_dataset(config, "eval_set_holdout.json", role="holdout", is_experimental=is_experimental)


if __name__ == "__main__":
    from config import CONFIG
    print("Testing evaluation harness with active configuration...")
    res = evaluate_config(CONFIG, is_experimental=True)
    print(f"Test Score: {res['aggregate_score']} | Latency: {res['avg_latency_ms']}ms | Grounding: {res['grounding_rate']}")
