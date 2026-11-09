"""
engine/evaluation/base.py
Standard evaluation data models and abstract EvaluationProvider interface for AutoTune 2.0.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


@dataclass
class EvalSample:
    """
    Standard evaluation sample representing a single query, context, and generation step.
    """
    id: str
    question: str
    generated_answer: str
    retrieved_contexts: List[str] = field(default_factory=list)
    retrieval_scores: List[float] = field(default_factory=list)
    
    # Ground truth reference data (optional for blind or uncurated evaluation)
    reference_answer: Optional[str] = None
    reference_contexts: Optional[List[str]] = None
    expected_terms: List[str] = field(default_factory=list)
    expected_claims: List[str] = field(default_factory=list)
    answerable: bool = True
    category: str = "general"
    
    # Execution telemetry
    latency_ms: float = 0.0
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    is_error: bool = False
    error_info: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuestionEvaluationResult:
    """
    Granular evaluation result for a single question.
    """
    sample_id: str
    question: str
    generated_answer: str
    expected_answer: Optional[str]
    retrieved_contexts: List[str]
    retrieval_scores: List[float]
    
    # Deterministic metrics
    expected_term_pass_rate: Optional[float] = None
    exact_match: Optional[float] = None
    numerical_grounding_passed: Optional[bool] = None
    ungrounded_numbers: List[str] = field(default_factory=list)
    citation_present: bool = False
    
    # Semantic & RAG metrics (None if judge not run or missing references)
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    
    # Performance telemetry
    latency_ms: float = 0.0
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    tokens: int = 0
    cost: float = 0.0
    
    # Failure categorization & status
    is_error: bool = False
    failure_category: Optional[str] = None
    # Allowed failure categories:
    # 'retrieval_failure', 'missing_context', 'poor_ranking', 'generation_failure',
    # 'hallucination', 'citation_failure', 'irrelevant_answer', 'latency_problem',
    # 'unanswerable_violation', 'infrastructure_error'
    
    error_info: Optional[Dict[str, Any]] = None
    evaluation_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregateEvaluationReport:
    """
    Comprehensive evaluation summary across a dataset.
    """
    dataset_id: str
    dataset_role: str  # 'tuning', 'validation', 'holdout', 'regression'
    dataset_version: str
    total_samples: int
    evaluator_name: str
    evaluator_version: str
    judge_model: Optional[str] = None
    
    # Deterministic summary
    expected_term_pass_rate: Optional[float] = None
    exact_match_rate: Optional[float] = None
    numerical_grounding_rate: Optional[float] = None
    citation_rate: Optional[float] = None
    
    # Semantic RAG summary (None if unavailable/not evaluated)
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    
    # Performance summary (P50, P95, averages)
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    avg_retrieval_ms: float = 0.0
    avg_generation_ms: float = 0.0
    avg_tokens_per_query: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    error_count: int = 0
    error_rate: float = 0.0
    
    # Objective and legacy compatibility
    composite_score: float = 0.0
    objective_score: float = 0.0
    
    # Per-sample question records
    question_results: List[QuestionEvaluationResult] = field(default_factory=list)
    failure_distribution: Dict[str, int] = field(default_factory=dict)


class BaseEvaluationProvider(ABC):
    """
    Common evaluator interface for AutoTune 2.0 evaluation providers.
    """
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the evaluation provider."""
        pass

    @property
    @abstractmethod
    def provider_version(self) -> str:
        """Version of the evaluation provider."""
        pass

    @abstractmethod
    def evaluate_sample(self, sample: EvalSample) -> QuestionEvaluationResult:
        """Evaluates a single sample across retrieval, generation, grounding and performance."""
        pass

    @abstractmethod
    def evaluate_batch(self, samples: List[EvalSample], dataset_id: str = "dataset", dataset_role: str = "tuning") -> AggregateEvaluationReport:
        """Evaluates a collection of samples and produces an aggregate report."""
        pass

