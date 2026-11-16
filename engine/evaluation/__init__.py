"""
engine/evaluation/__init__.py
AutoTune 2.0 Evaluation Engine Package.
Provides modular, multi-metric evaluation across deterministic, semantic, performance, and grounding dimensions.
"""
from evaluation.base import (
    EvalSample,
    QuestionEvaluationResult,
    AggregateEvaluationReport,
    BaseEvaluationProvider
)
from evaluation.deterministic_metrics import (
    compute_expected_term_pass_rate,
    compute_exact_match,
    verify_numerical_grounding,
    verify_citation_coverage,
    categorize_question_failure
)
from evaluation.performance_metrics import (
    calculate_percentile,
    compute_performance_metrics
)
from evaluation.judge_provider import SemanticJudgeProvider
from evaluation.evaluator_registry import AutoTuneEvaluationProvider
from evaluation.dataset_manager import DatasetManager
from evaluation.objectives import OptimizationObjective
from evaluation.evaluation_service import EvaluationService

__all__ = [
    "EvalSample",
    "QuestionEvaluationResult",
    "AggregateEvaluationReport",
    "BaseEvaluationProvider",
    "AutoTuneEvaluationProvider",
    "DatasetManager",
    "OptimizationObjective",
    "EvaluationService",
    "SemanticJudgeProvider",
    "compute_expected_term_pass_rate",
    "compute_exact_match",
    "verify_numerical_grounding",
    "verify_citation_coverage",
    "categorize_question_failure",
    "calculate_percentile",
    "compute_performance_metrics"
]

