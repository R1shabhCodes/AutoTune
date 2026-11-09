"""
engine/evaluation/evaluation_service.py
Core Evaluation Service for AutoTune 2.0.
Coordinates dataset loading, RAG pipeline execution, deterministic/semantic evaluation,
and structured reporting with backward-compatibility for Phase 1 and apps/rag_finance.
"""
import os
import sys
import time
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rag_pipeline
from evaluation.base import EvalSample, AggregateEvaluationReport, QuestionEvaluationResult
from evaluation.dataset_manager import DatasetManager
from evaluation.evaluator_registry import AutoTuneEvaluationProvider
from evaluation.objectives import OptimizationObjective


class EvaluationService:
    """
    Central evaluation orchestrator for AutoTune 2.0.
    """
    def __init__(self, run_semantic_judge: bool = False, judge_model: Optional[str] = None):
        self.dataset_manager = DatasetManager()
        self.provider = AutoTuneEvaluationProvider(
            run_semantic_judge=run_semantic_judge,
            judge_model=judge_model
        )

    def evaluate_configuration(
        self,
        config: Dict[str, Any],
        dataset_filename: str = "eval_set_tuning.json",
        role: str = "tuning",
        is_experimental: bool = True
    ) -> AggregateEvaluationReport:
        """
        Executes an end-to-end evaluation run of a configuration against a dataset.
        Reuses cached index when chunk parameters are unchanged.
        """
        engine_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dataset = self.dataset_manager.load_dataset(dataset_filename, role=role)
        dataset_hash = self.dataset_manager.compute_dataset_hash(dataset)

        chunk_size = int(config.get("chunk_size", 500))
        chunk_overlap = int(config.get("chunk_overlap", 50))
        top_k = int(config.get("top_k", 3))
        retrieval_strategy = config.get("retrieval_strategy", "vector")
        prompt_tmpl = config.get(
            "prompt_template",
            "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        )
        temperature = float(config.get("temperature", 0.0))

        # Build or retrieve cached index namespace
        collection_name = rag_pipeline.build_index(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            is_experimental=is_experimental
        )
        corpus_dir = os.path.join(engine_dir, "corpus")
        cache_key = rag_pipeline.get_index_cache_key(chunk_size, chunk_overlap, corpus_dir)

        samples: List[EvalSample] = []

        for idx, item in enumerate(dataset):
            q_id = item["id"]
            question = item["question"]
            expected_terms = item.get("expected_answer_contains", [])
            ref_ans = item.get("reference_answer")
            ref_ctx = item.get("reference_contexts")
            answerable = item.get("answerable", True)
            category = item.get("category", "general")

            # 1. Retrieve
            t_ret_start = time.time()
            chunks = rag_pipeline.retrieve(
                question,
                top_k=top_k,
                strategy=retrieval_strategy,
                collection_name=collection_name,
                cache_key=cache_key
            )
            retrieval_ms = (time.time() - t_ret_start) * 1000

            # 2. Generate
            t_gen_start = time.time()
            gen_ans, gen_is_err, gen_err_info = rag_pipeline.generate(
                query=question,
                chunks=chunks,
                prompt_template=prompt_tmpl,
                temperature=temperature,
                return_metadata=True
            )
            generation_ms = (time.time() - t_gen_start) * 1000
            total_latency_ms = retrieval_ms + generation_ms

            # Approximate tokens
            prompt_text = prompt_tmpl.replace("{context}", "\n\n".join(chunks) if chunks else "").replace("{question}", question)
            tokens = (len(prompt_text) + len(gen_ans)) // 4

            sample = EvalSample(
                id=q_id,
                question=question,
                generated_answer=gen_ans,
                retrieved_contexts=chunks,
                retrieval_scores=[],
                reference_answer=ref_ans,
                reference_contexts=ref_ctx,
                expected_terms=expected_terms,
                answerable=answerable,
                category=category,
                latency_ms=round(total_latency_ms, 1),
                retrieval_ms=round(retrieval_ms, 1),
                generation_ms=round(generation_ms, 1),
                tokens=tokens,
                is_error=gen_is_err,
                error_info=gen_err_info
            )
            samples.append(sample)

        # Produce aggregate evaluation report
        report = self.provider.evaluate_batch(
            samples=samples,
            dataset_id=dataset_filename,
            dataset_role=role,
            dataset_version=f"v_{dataset_hash}"
        )
        return report

    def to_legacy_eval_dict(self, report: AggregateEvaluationReport) -> Dict[str, Any]:
        """
        Adapts an AggregateEvaluationReport to the legacy eval_harness dictionary format
        so existing agent_loop, FastAPI endpoints, and Streamlit app work seamlessly.
        """
        results_legacy = []
        for qr in report.question_results:
            results_legacy.append({
                "question": qr.question,
                "expected_terms": qr.expected_answer.split(", ") if qr.expected_answer else [],
                "expected": qr.expected_answer.split(", ") if qr.expected_answer else [],
                "generated_answer": qr.generated_answer,
                "actual_answer": qr.generated_answer,
                "score": qr.expected_term_pass_rate if qr.expected_term_pass_rate is not None else 0.0,
                "passed": bool(qr.expected_term_pass_rate is not None and qr.expected_term_pass_rate >= 1.0 and not qr.is_error),
                "is_error": qr.is_error,
                "error_info": qr.error_info,
                "citation_present": qr.citation_present,
                "latency_ms": qr.latency_ms,
                "retrieval_ms": qr.retrieval_ms,
                "generation_ms": qr.generation_ms,
                "tokens": qr.tokens,
                "grounding_passed": qr.numerical_grounding_passed,
                "ungrounded_numbers": qr.ungrounded_numbers,
                "failure_category": qr.failure_category
            })

        is_infra_err = bool(report.error_count == report.total_samples and report.total_samples > 0)
        first_err = next((qr.error_info for qr in report.question_results if qr.is_error), None)

        return {
            "aggregate_score": report.expected_term_pass_rate or 0.0,
            "expected_term_pass_rate": report.expected_term_pass_rate or 0.0,
            "composite_score": report.composite_score,
            "avg_latency_ms": report.avg_latency_ms,
            "p50_latency_ms": report.p50_latency_ms,
            "p95_latency_ms": report.p95_latency_ms,
            "avg_retrieval_ms": report.avg_retrieval_ms,
            "avg_generation_ms": report.avg_generation_ms,
            "avg_tokens_per_query": report.avg_tokens_per_query,
            "total_tokens": report.total_tokens,
            "grounding_rate": report.numerical_grounding_rate or 0.0,
            "citation_rate": report.citation_rate or 0.0,
            "faithfulness": report.faithfulness,
            "answer_relevancy": report.answer_relevancy,
            "context_precision": report.context_precision,
            "context_recall": report.context_recall,
            "error_count": report.error_count,
            "is_infrastructure_error": is_infra_err,
            "infrastructure_error_info": first_err,
            "evaluator_name": report.evaluator_name,
            "evaluator_version": report.evaluator_version,
            "judge_model": report.judge_model,
            "failure_distribution": report.failure_distribution,
            "results": results_legacy
        }

