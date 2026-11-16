"""
Unit tests for AutoTune 2.0 Evaluation Engine (Phase 2).
Covers:
1. Deterministic term pass rate, exact match, and numerical grounding.
2. Latency percentiles (P50, P95) and performance metrics.
3. Dataset manager loading, schema validation, and holdout isolation.
4. Semantic judge interface and handling of missing references (None vs zero).
5. Objective evaluation and constraint satisfaction.
6. Question-level evaluation persistence and schema integrity.
7. Compatibility with finance RAG pipeline outputs.
"""
import unittest
import os
import sys
import tempfile
import json

# Ensure engine is on path for runtime execution
engine_path = os.path.join(os.path.dirname(__file__), "..", "engine")
if engine_path not in sys.path:
    sys.path.insert(0, engine_path)

from engine.evaluation import (
    EvalSample,
    QuestionEvaluationResult,
    AggregateEvaluationReport,
    AutoTuneEvaluationProvider,
    DatasetManager,
    OptimizationObjective,
    EvaluationService,
    SemanticJudgeProvider,
    compute_expected_term_pass_rate,
    compute_exact_match,
    verify_numerical_grounding,
    verify_citation_coverage,
    categorize_question_failure,
    calculate_percentile,
    compute_performance_metrics
)
from engine import db


class TestEvaluationEngine2(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_eval.db")
        db.apply_migrations(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deterministic_term_pass_rate(self):
        """Pass rate accurately measures expected term containment."""
        rate, matched, total = compute_expected_term_pass_rate(
            "The STCG tax rate was changed to 20% in Budget 2024.",
            ["20%"]
        )
        self.assertEqual(rate, 1.0)
        self.assertEqual(matched, 1)

        rate, matched, total = compute_expected_term_pass_rate(
            "The four types of GST are CGST, SGST, and IGST.",
            ["CGST", "SGST", "IGST", "UTGST"]
        )
        self.assertEqual(rate, 0.75)
        self.assertEqual(matched, 3)

    def test_exact_match(self):
        """Exact match normalizes whitespace and punctuation."""
        em = compute_exact_match("  Net Asset Value! ", "net asset value")
        self.assertEqual(em, 1.0)
        em = compute_exact_match("Different answer", "net asset value")
        self.assertEqual(em, 0.0)

    def test_numerical_grounding_verification(self):
        """Numerical grounding flags numbers in the answer not present in the contexts."""
        contexts = ["Section 80C provides a maximum deduction limit of 1.5 lakh or 150,000."]
        
        # Grounded answer
        passed, ungrounded = verify_numerical_grounding(
            "Under Section 80C, deduction limit is 1.5 lakh (150,000).", contexts
        )
        self.assertTrue(passed)
        self.assertEqual(ungrounded, [])

        # Hallucinated number
        passed, ungrounded = verify_numerical_grounding(
            "Under Section 80C, deduction limit is 250,000 and 1.5 lakh.", contexts
        )
        self.assertFalse(passed)
        self.assertIn("250,000", ungrounded)

    def test_performance_percentiles(self):
        """Latency percentiles P50 and P95 are calculated properly."""
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0]
        samples = [EvalSample(id=str(i), question="q", generated_answer="a", latency_ms=l, tokens=100) for i, l in enumerate(latencies)]
        
        perf = compute_performance_metrics(samples)
        self.assertEqual(perf["avg_latency_ms"], 550.0)
        self.assertAlmostEqual(perf["p50_latency_ms"], 550.0, delta=10.0)
        self.assertGreater(perf["p95_latency_ms"], 900.0)
        self.assertEqual(perf["total_tokens"], 1000)
        self.assertEqual(perf["error_count"], 0)

    def test_dataset_manager_validation_and_leakage(self):
        """DatasetManager validates schema and detects holdout data leakage."""
        mgr = DatasetManager(base_dir=self.temp_dir.name)
        
        tuning_file = os.path.join(self.temp_dir.name, "tuning.json")
        holdout_file = os.path.join(self.temp_dir.name, "holdout.json")
        
        with open(tuning_file, "w", encoding="utf-8") as f:
            json.dump([
                {"question": "What is the inflation target?", "expected_answer_contains": ["4%"]}
            ], f)
            
        with open(holdout_file, "w", encoding="utf-8") as f:
            json.dump([
                {"question": "What is the standard deduction?", "expected_answer_contains": ["75,000"]}
            ], f)

        tuning_data = mgr.load_dataset(tuning_file, role="tuning")
        holdout_data = mgr.load_dataset(holdout_file, role="holdout")
        
        self.assertTrue(mgr.validate_holdout_isolation(tuning_data, holdout_data))
        
        # Introduce leak
        leaked_holdout = [{"question": "What is the inflation target?", "expected_answer_contains": ["4%"]}]
        self.assertFalse(mgr.validate_holdout_isolation(tuning_data, leaked_holdout))

    def test_missing_metrics_represented_as_none_not_zero(self):
        """Missing ground-truth references result in None for context recall, never zero."""
        judge = SemanticJudgeProvider(model_name="mock-judge")
        sample_without_reference = EvalSample(
            id="q1",
            question="What is fiscal deficit?",
            generated_answer="Fiscal deficit is 4.9%.",
            retrieved_contexts=["Budget target is 4.9%."]
            # reference_answer and reference_contexts are None
        )
        recall = judge.evaluate_context_recall(sample_without_reference)
        self.assertIsNone(recall, "Missing reference context must return None, not 0.0")

    def test_objective_evaluation_and_constraints(self):
        """OptimizationObjective enforces constraints before accepting candidate improvement."""
        obj = OptimizationObjective({
            "primary": "composite_score",
            "direction": "maximize",
            "constraints": {
                "error_rate_max": 0.0,
                "numerical_grounding_min": 0.80
            }
        })

        base_report = AggregateEvaluationReport(
            dataset_id="test", dataset_role="tuning", dataset_version="1", total_samples=5,
            evaluator_name="test", evaluator_version="1",
            composite_score=0.70, numerical_grounding_rate=0.85, error_rate=0.0
        )

        # Candidate with higher composite score but violating grounding constraint
        cand_violating = AggregateEvaluationReport(
            dataset_id="test", dataset_role="tuning", dataset_version="1", total_samples=5,
            evaluator_name="test", evaluator_version="1",
            composite_score=0.85, numerical_grounding_rate=0.60, error_rate=0.0
        )
        accepted, reason, diff = obj.evaluate_candidate(cand_violating, base_report)
        self.assertFalse(accepted)
        self.assertIn("Constraint violated", reason)

        # Valid improving candidate
        cand_improving = AggregateEvaluationReport(
            dataset_id="test", dataset_role="tuning", dataset_version="1", total_samples=5,
            evaluator_name="test", evaluator_version="1",
            composite_score=0.80, numerical_grounding_rate=0.90, error_rate=0.0
        )
        accepted, reason, diff = obj.evaluate_candidate(cand_improving, base_report)
        self.assertTrue(accepted)
        self.assertIn("Improvement achieved", reason)

    def test_save_and_retrieve_question_evaluations(self):
        """Granular question-level telemetry is saved and retrieved from SQLite."""
        q_result = QuestionEvaluationResult(
            sample_id="q_001",
            question="What is the repo rate?",
            generated_answer="The repo rate is 6.50%.",
            expected_answer="6.50%",
            retrieved_contexts=["RBI repo rate stands at 6.50%."],
            retrieval_scores=[0.92],
            expected_term_pass_rate=1.0,
            numerical_grounding_passed=True,
            latency_ms=125.4,
            tokens=45
        )

        db.save_question_evaluations(
            trial_id="trial_exp1_1",
            experiment_id="exp1",
            iteration_number=1,
            question_results=[q_result],
            db_path=self.db_path
        )

        records = db.get_question_evaluations_for_trial("trial_exp1_1", db_path=self.db_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["question"], "What is the repo rate?")
        self.assertEqual(records[0]["expected_term_pass_rate"], 1.0)
        self.assertEqual(records[0]["numerical_grounding_passed"], 1)


if __name__ == "__main__":
    unittest.main()

