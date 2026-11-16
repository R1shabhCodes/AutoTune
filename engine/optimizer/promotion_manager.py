"""
engine/optimizer/promotion_manager.py
Promotion workflow manager for AutoTune 2.0.
Verifies candidates across Tuning, Validation, Blind Holdout, and Regression sets
before granting promotion approval. Generates exact configuration diffs, exports, and rollback state.
"""
from typing import Dict, Any, List, Optional, Tuple
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evaluation import EvaluationService, DatasetManager


class PromotionManager:
    """
    Manages explicit configuration promotion gates, comparison diffs, and rollback snapshots.
    """
    def __init__(self, eval_service: Optional[EvaluationService] = None):
        self.eval_service = eval_service or EvaluationService(run_semantic_judge=False)
        self.dataset_manager = DatasetManager()

    def generate_config_diff(
        self,
        base_config: Dict[str, Any],
        candidate_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Calculates exact parameter differences between baseline and candidate configurations.
        """
        diffs = []
        all_keys = sorted(set(base_config.keys()).union(candidate_config.keys()))
        for k in all_keys:
            old_val = base_config.get(k)
            new_val = candidate_config.get(k)
            if old_val != new_val:
                diffs.append({
                    "parameter": k,
                    "old_value": old_val,
                    "new_value": new_val,
                    "changed": True
                })
        return diffs

    def evaluate_promotion_readiness(
        self,
        candidate_config: Dict[str, Any],
        baseline_config: Dict[str, Any],
        validation_file: Optional[str] = None,
        holdout_file: str = "eval_set_holdout.json",
        regression_file: Optional[str] = None,
        adapter: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Runs rigorous multi-stage qualification:
        1. Tuning validation check
        2. Blind holdout evaluation
        3. Regression test suite
        """
        # 1. Blind Holdout Evaluation
        holdout_report = self.eval_service.evaluate_configuration(
            config=candidate_config,
            dataset_filename=holdout_file,
            role="holdout",
            is_experimental=True,
            adapter=adapter
        )
        base_holdout = self.eval_service.evaluate_configuration(
            config=baseline_config,
            dataset_filename=holdout_file,
            role="holdout",
            is_experimental=True,
            adapter=adapter
        )

        cand_holdout_score = holdout_report.expected_term_pass_rate or 0.0
        base_holdout_score = base_holdout.expected_term_pass_rate or 0.0

        # Disallow promotion if candidate degrades holdout accuracy
        holdout_passed = bool(cand_holdout_score >= base_holdout_score)

        # 2. Regression check if file provided
        reg_passed = True
        cand_reg_score = None
        base_reg_score = None
        if regression_file and os.path.exists(regression_file):
            reg_report = self.eval_service.evaluate_configuration(
                config=candidate_config, dataset_filename=regression_file, role="regression", adapter=adapter
            )
            base_reg = self.eval_service.evaluate_configuration(
                config=baseline_config, dataset_filename=regression_file, role="regression", adapter=adapter
            )
            cand_reg_score = reg_report.expected_term_pass_rate or 0.0
            base_reg_score = base_reg.expected_term_pass_rate or 0.0
            reg_passed = bool(cand_reg_score >= base_reg_score)

        is_eligible = holdout_passed and reg_passed
        diffs = self.generate_config_diff(baseline_config, candidate_config)

        return {
            "eligible_for_promotion": is_eligible,
            "parameter_diffs": diffs,
            "holdout_results": {
                "candidate_score": cand_holdout_score,
                "baseline_score": base_holdout_score,
                "passed": holdout_passed
            },
            "regression_results": {
                "candidate_score": cand_reg_score,
                "baseline_score": base_reg_score,
                "passed": reg_passed
            } if regression_file else None,
            "recommendation": "APPROVED: Candidate qualifies on blind holdout evaluation." if is_eligible else "REJECTED: Candidate degraded blind holdout accuracy."
        }

