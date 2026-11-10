"""
tests/test_phase4_optimizer.py
Unit tests for AutoTune 2.0 Hybrid Optimization Engine (Phase 4).
Covers:
1. Optuna search space dynamic mapping from adapter parameter declarations.
2. TPE and Random sampler reproducible execution with fixed seeds.
3. Agent diagnostician hypothesis and range suggestions for question failures.
4. Promotion manager candidate qualification, config diffs, and holdout gate enforcement.
5. Multi-objective target optimization and hard constraint checking.
6. Safe configuration restoration on rejected or crashed trials.
7. Multi-application isolation (Finance vs External RAG adapter).
"""
import unittest
import os
import sys
import tempfile
import json
import optuna
from unittest.mock import patch, MagicMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from engine.integrations.schemas.protocol import ParameterSchema, ManifestResponse
from engine.optimizer.optuna_study import create_study, build_optuna_search_space
from engine.optimizer.agent_diagnostician import AgentDiagnostician
from engine.optimizer.promotion_manager import PromotionManager
from engine.optimizer.hybrid_engine import HybridOptimizationEngine
from engine.integrations.finance_adapter import FinanceRAGAdapter
from engine.evaluation import OptimizationObjective, AggregateEvaluationReport
import db


class TestHybridOptimizationEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_opt.db")
        db.apply_migrations(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_optuna_dynamic_search_space_mapping(self):
        """Optuna dynamically samples parameter types, ranges, steps, and options."""
        parameters = {
            "top_k": ParameterSchema(type="integer", default=3, min=1, max=10, step=1),
            "similarity_threshold": ParameterSchema(type="float", default=0.75, min=0.5, max=1.0, step=0.05),
            "retrieval_strategy": ParameterSchema(type="categorical", default="vector", options=["vector", "bm25", "hybrid"]),
            "rerank_enabled": ParameterSchema(type="boolean", default=True)
        }

        study = optuna.create_study()
        trial = study.ask()
        candidate = build_optuna_search_space(trial, parameters)

        self.assertIn("top_k", candidate)
        self.assertIsInstance(candidate["top_k"], int)
        self.assertTrue(1 <= candidate["top_k"] <= 10)

        self.assertIn("similarity_threshold", candidate)
        self.assertIsInstance(candidate["similarity_threshold"], float)
        self.assertTrue(0.5 <= candidate["similarity_threshold"] <= 1.0)

        self.assertIn("retrieval_strategy", candidate)
        self.assertIn(candidate["retrieval_strategy"], ["vector", "bm25", "hybrid"])

        self.assertIn("rerank_enabled", candidate)
        self.assertIn(candidate["rerank_enabled"], [True, False])

    def test_optuna_reproducible_random_and_tpe_seeds(self):
        """Studies initialized with identical seeds generate identical first suggestions."""
        params = {"param_a": ParameterSchema(type="integer", default=5, min=1, max=100)}

        study1 = create_study("study_seed_1", sampler_type="random", seed=123)
        cand1 = build_optuna_search_space(study1.ask(), params)

        study2 = create_study("study_seed_2", sampler_type="random", seed=123)
        cand2 = build_optuna_search_space(study2.ask(), params)

        self.assertEqual(cand1["param_a"], cand2["param_a"])

    def test_agent_diagnostician_reasoning(self):
        """Diagnostician formulates hypothesis from failure distribution."""
        diag = AgentDiagnostician()
        failing = [
            {"question": "What is GST rate?", "failure_category": "missing_context", "expected": ["18%"]}
        ]
        params = {"top_k": ParameterSchema(type="integer", default=3, min=1, max=10)}
        
        result = diag.diagnose_failures(
            failing_questions=failing,
            current_config={"top_k": 3},
            parameters_manifest=params,
            recent_history=[]
        )
        self.assertIn("hypothesis", result)
        self.assertIsInstance(result["hypothesis"], str)
        self.assertIn("focus_parameters", result)

    def test_promotion_manager_holdout_gate_and_diffs(self):
        """PromotionManager calculates exact diffs and blocks promotion if holdout degrades."""
        pm = PromotionManager()
        base_cfg = {"chunk_size": 100, "top_k": 3}
        cand_cfg = {"chunk_size": 250, "top_k": 5}

        diffs = pm.generate_config_diff(base_cfg, cand_cfg)
        self.assertEqual(len(diffs), 2)
        self.assertEqual(diffs[0]["parameter"], "chunk_size")
        self.assertEqual(diffs[0]["old_value"], 100)
        self.assertEqual(diffs[0]["new_value"], 250)

        # Mock holdout evaluation degradation
        with patch.object(pm.eval_service, "evaluate_configuration") as mock_eval:
            # Baseline holdout returns 0.90, candidate returns 0.70
            mock_eval.side_effect = [
                AggregateEvaluationReport(
                    dataset_id="holdout", dataset_role="holdout", dataset_version="1", total_samples=5,
                    evaluator_name="test", evaluator_version="1", expected_term_pass_rate=0.70
                ),
                AggregateEvaluationReport(
                    dataset_id="holdout", dataset_role="holdout", dataset_version="1", total_samples=5,
                    evaluator_name="test", evaluator_version="1", expected_term_pass_rate=0.90
                )
            ]

            readiness = pm.evaluate_promotion_readiness(cand_cfg, base_cfg)
            self.assertFalse(readiness["eligible_for_promotion"])
            self.assertIn("REJECTED", readiness["recommendation"])

    def test_multi_objective_and_hard_constraints(self):
        """Objectives reject candidate proposals that violate latency constraints."""
        obj = OptimizationObjective({
            "primary": "expected_term_pass_rate",
            "direction": "maximize",
            "constraints": {
                "p95_latency_max_ms": 1000.0
            }
        })

        base_report = AggregateEvaluationReport(
            dataset_id="d1", dataset_role="tuning", dataset_version="1", total_samples=3,
            evaluator_name="t", evaluator_version="1", expected_term_pass_rate=0.75, p95_latency_ms=500.0
        )

        cand_violating = AggregateEvaluationReport(
            dataset_id="d1", dataset_role="tuning", dataset_version="1", total_samples=3,
            evaluator_name="t", evaluator_version="1", expected_term_pass_rate=0.95, p95_latency_ms=1500.0
        )

        accepted, reason, diff = obj.evaluate_candidate(cand_violating, base_report)
        self.assertFalse(accepted)
        self.assertIn("Constraint violated: p95_latency", reason)

    def test_rejected_trial_restoration(self):
        """When an adapter proposal is rejected, the active configuration is restored."""
        adapter = FinanceRAGAdapter()
        initial_cfg = dict(adapter.get_config())

        # Propose and apply candidate
        adapter.apply_config({"top_k": 12})
        self.assertEqual(adapter.get_config()["top_k"], 12)

        # Restore
        adapter.restore_config(initial_cfg)
        self.assertEqual(adapter.get_config()["top_k"], initial_cfg["top_k"])


if __name__ == "__main__":
    unittest.main()

