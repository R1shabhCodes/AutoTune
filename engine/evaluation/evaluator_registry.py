"""
engine/evaluation/evaluator_registry.py
Default Composite Evaluation Provider combining Deterministic, Performance, and Semantic metrics.
"""
from typing import List, Dict, Any, Optional
from evaluation.base import (
    BaseEvaluationProvider,
    EvalSample,
    QuestionEvaluationResult,
    AggregateEvaluationReport
)
from evaluation.deterministic_metrics import (
    compute_expected_term_pass_rate,
    compute_exact_match,
    verify_numerical_grounding,
    verify_citation_coverage,
    categorize_question_failure
)
from evaluation.performance_metrics import compute_performance_metrics
from evaluation.judge_provider import SemanticJudgeProvider


class AutoTuneEvaluationProvider(BaseEvaluationProvider):
    """
    Standard Evaluation Provider for AutoTune 2.0.
    Executes multi-dimensional evaluation:
    1. Deterministic term and numerical grounding verification.
    2. Exact matching when references are available.
    3. Performance telemetry (latency percentiles, tokens, errors).
    4. Semantic RAG metrics (faithfulness, relevancy) with explicit judge tracking.
    """
    def __init__(self, run_semantic_judge: bool = False, judge_model: Optional[str] = None):
        self._provider_name = "AutoTune-StandardEvaluator"
        self._provider_version = "2.0.0"
        self.run_semantic_judge = run_semantic_judge
        self.judge = SemanticJudgeProvider(model_name=judge_model) if run_semantic_judge else None

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def provider_version(self) -> str:
        return self._provider_version

    def evaluate_sample(self, sample: EvalSample) -> QuestionEvaluationResult:
        # 1. Deterministic term pass rate
        term_pass_rate, matched_count, total_expected = compute_expected_term_pass_rate(
            sample.generated_answer, sample.expected_terms
        )
        
        # 2. Exact match
        exact_match = compute_exact_match(sample.generated_answer, sample.reference_answer)
        
        # 3. Numerical grounding
        num_grounded, ungrounded_nums = verify_numerical_grounding(
            sample.generated_answer, sample.retrieved_contexts
        )
        
        # 4. Citation presence
        citation_present = verify_citation_coverage(sample.generated_answer)
        
        # 5. Semantic metrics (optional or on-demand)
        faithfulness = None
        relevancy = None
        context_precision = None
        context_recall = None
        
        if self.judge and self.run_semantic_judge:
            faithfulness = self.judge.evaluate_faithfulness(sample)
            relevancy = self.judge.evaluate_answer_relevancy(sample)
            context_precision = self.judge.evaluate_context_precision(sample)
            context_recall = self.judge.evaluate_context_recall(sample)

        # 6. Failure classification
        failure_cat = categorize_question_failure(
            sample=sample,
            term_pass_rate=term_pass_rate,
            numerical_grounded=num_grounded,
            citation_present=citation_present,
            is_error=sample.is_error
        )

        return QuestionEvaluationResult(
            sample_id=sample.id,
            question=sample.question,
            generated_answer=sample.generated_answer,
            expected_answer=sample.reference_answer or (", ".join(sample.expected_terms) if sample.expected_terms else None),
            retrieved_contexts=sample.retrieved_contexts,
            retrieval_scores=sample.retrieval_scores,
            expected_term_pass_rate=term_pass_rate,
            exact_match=exact_match,
            numerical_grounding_passed=num_grounded,
            ungrounded_numbers=ungrounded_nums,
            citation_present=citation_present,
            faithfulness=faithfulness,
            answer_relevancy=relevancy,
            context_precision=context_precision,
            context_recall=context_recall,
            latency_ms=sample.latency_ms,
            retrieval_ms=sample.retrieval_ms,
            generation_ms=sample.generation_ms,
            tokens=sample.tokens,
            cost=sample.cost,
            is_error=sample.is_error,
            failure_category=failure_cat,
            error_info=sample.error_info,
            evaluation_metadata={"category": sample.category, "answerable": sample.answerable}
        )

    def evaluate_batch(
        self,
        samples: List[EvalSample],
        dataset_id: str = "eval_set_tuning",
        dataset_role: str = "tuning",
        dataset_version: str = "1.0.0"
    ) -> AggregateEvaluationReport:
        if not samples:
            return AggregateEvaluationReport(
                dataset_id=dataset_id,
                dataset_role=dataset_role,
                dataset_version=dataset_version,
                total_samples=0,
                evaluator_name=self.provider_name,
                evaluator_version=self.provider_version
            )

        question_results: List[QuestionEvaluationResult] = []
        failures: Dict[str, int] = {}

        for sample in samples:
            res = self.evaluate_sample(sample)
            question_results.append(res)
            if res.failure_category:
                failures[res.failure_category] = failures.get(res.failure_category, 0) + 1

        total = len(question_results)
        term_passes = [r.expected_term_pass_rate for r in question_results if r.expected_term_pass_rate is not None]
        avg_term_pass = round(sum(term_passes) / len(term_passes), 4) if term_passes else 0.0

        exact_matches = [r.exact_match for r in question_results if r.exact_match is not None]
        avg_exact = round(sum(exact_matches) / len(exact_matches), 4) if exact_matches else 0.0

        grounded_count = sum(1 for r in question_results if r.numerical_grounding_passed)
        grounding_rate = round(grounded_count / total, 4)

        citation_count = sum(1 for r in question_results if r.citation_present)
        citation_rate = round(citation_count / total, 4)

        # Performance summary
        perf = compute_performance_metrics(question_results)

        # Semantic metrics (only compute average over non-None values; if all None, remain None)
        faith_vals = [r.faithfulness for r in question_results if r.faithfulness is not None]
        avg_faith = round(sum(faith_vals) / len(faith_vals), 4) if faith_vals else None

        rel_vals = [r.answer_relevancy for r in question_results if r.answer_relevancy is not None]
        avg_rel = round(sum(rel_vals) / len(rel_vals), 4) if rel_vals else None

        cp_vals = [r.context_precision for r in question_results if r.context_precision is not None]
        avg_cp = round(sum(cp_vals) / len(cp_vals), 4) if cp_vals else None

        cr_vals = [r.context_recall for r in question_results if r.context_recall is not None]
        avg_cr = round(sum(cr_vals) / len(cr_vals), 4) if cr_vals else None

        # Composite score calculation (deterministic baseline compatible)
        # Latency penalty: 1.0 - (latency / 60000) clamped
        lat_norm = max(0.0, min(1.0, 1.0 - (perf["avg_latency_ms"] / 60000.0)))
        # Token penalty: 1.0 - (tokens / 10000) clamped
        tok_norm = max(0.0, min(1.0, 1.0 - (perf["avg_tokens_per_query"] / 10000.0)))

        composite = (
            0.60 * avg_term_pass +
            0.15 * grounding_rate +
            0.15 * lat_norm +
            0.10 * tok_norm
        )
        composite = round(composite, 4)

        return AggregateEvaluationReport(
            dataset_id=dataset_id,
            dataset_role=dataset_role,
            dataset_version=dataset_version,
            total_samples=total,
            evaluator_name=self.provider_name,
            evaluator_version=self.provider_version,
            judge_model=self.judge.model_name if self.judge else None,
            expected_term_pass_rate=avg_term_pass,
            exact_match_rate=avg_exact,
            numerical_grounding_rate=grounding_rate,
            citation_rate=citation_rate,
            faithfulness=avg_faith,
            answer_relevancy=avg_rel,
            context_precision=avg_cp,
            context_recall=avg_cr,
            avg_latency_ms=perf["avg_latency_ms"],
            p50_latency_ms=perf["p50_latency_ms"],
            p95_latency_ms=perf["p95_latency_ms"],
            avg_retrieval_ms=perf["avg_retrieval_ms"],
            avg_generation_ms=perf["avg_generation_ms"],
            avg_tokens_per_query=perf["avg_tokens_per_query"],
            total_tokens=perf["total_tokens"],
            total_cost=perf["total_cost"],
            error_count=perf["error_count"],
            error_rate=perf["error_rate"],
            composite_score=composite,
            objective_score=avg_term_pass,
            question_results=question_results,
            failure_distribution=failures
        )

