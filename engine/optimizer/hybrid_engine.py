"""
engine/optimizer/hybrid_engine.py
Hybrid Optimization Engine for AutoTune 2.0.
Combines:
- Optuna Bayesian/Random Parameter Exploration
- Qwen 2.5 1.5B LLM Diagnostic Reasoning
- Universal RAG Adapter Protocol Execution
- Multi-objective Target Evaluation and Hard Constraint Enforcement
- Isolated SQLite and State Management
"""
import os
import sys
import time
import json
import datetime
from typing import Dict, Any, List, Optional, Tuple, Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
from evaluation import EvaluationService, OptimizationObjective
from engine.integrations import BaseRAGAdapter, get_adapter_registry
from engine.optimizer.optuna_study import create_study, build_optuna_search_space
from engine.optimizer.agent_diagnostician import AgentDiagnostician
from engine.optimizer.promotion_manager import PromotionManager


class HybridOptimizationEngine:
    """
    Orchestrates systematic, reproducible parameter optimization combining Optuna search spaces
    and LLM agent failure diagnosis.
    """
    def __init__(
        self,
        adapter: Optional[BaseRAGAdapter] = None,
        db_path: Optional[str] = None
    ):
        self.adapter = adapter or get_adapter_registry().get_adapter("default")
        self.db_path = db_path or db.DB_PATH
        self.eval_service = EvaluationService(run_semantic_judge=False)
        self.diagnostician = AgentDiagnostician()
        self.promotion_manager = PromotionManager(self.eval_service)

    async def run_study(
        self,
        experiment_id: str,
        project_id: str = "default",
        dataset_filename: str = "eval_set_tuning.json",
        trial_budget: int = 5,
        sampler_type: str = "tpe",
        seed: int = 42,
        objective_spec: Optional[Dict[str, Any]] = None,
        on_iteration_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Runs an end-to-end hybrid optimization study.
        """
        manifest = self.adapter.get_manifest()
        if manifest.mode == "observe":
            raise RuntimeError(f"Application '{manifest.application}' is in Observe Mode. Cannot run optimization trials.")

        # Initialize objective engine
        objective_engine = OptimizationObjective(spec=objective_spec)

        # Baseline configuration
        baseline_config = self.adapter.get_config()
        active_config = dict(baseline_config)

        # 1. Run Baseline Evaluation (Trial 0)
        baseline_report = self.eval_service.evaluate_configuration(
            config=baseline_config,
            dataset_filename=dataset_filename,
            role="tuning",
            is_experimental=True,
            adapter=self.adapter
        )
        baseline_dict = self.eval_service.to_legacy_eval_dict(baseline_report)

        # Check existing max iteration
        conn = db.get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT MAX(iteration_number) FROM iterations")
        row = cur.fetchone()
        start_iter_num = (row[0] or 0) + 1
        conn.close()

        # Record Baseline Trial
        trial_0_id = f"trial_{experiment_id}_0"
        db.log_iteration(
            iter_num=start_iter_num,
            hypothesis="Baseline evaluation of initial configuration.",
            param="[Baseline]",
            old_val="N/A",
            new_val="N/A",
            old_score=0.0,
            new_score=baseline_report.expected_term_pass_rate or 0.0,
            accepted=True,
            motivated_by="",
            avg_latency_ms=baseline_report.avg_latency_ms,
            total_tokens=baseline_report.total_tokens,
            composite_score=baseline_report.composite_score,
            project_id=project_id,
            experiment_id=experiment_id,
            trial_id=trial_0_id,
            config_snapshot=baseline_config,
            score_improvement=0.0,
            rejection_reason="",
            proposal_status="baseline",
            db_path=self.db_path
        )
        if baseline_report.question_results:
            db.save_question_evaluations(
                trial_id=trial_0_id,
                experiment_id=experiment_id,
                iteration_number=start_iter_num,
                question_results=baseline_report.question_results,
                db_path=self.db_path
            )

        if on_iteration_callback:
            await on_iteration_callback({
                "iteration_number": start_iter_num,
                "hypothesis": "Baseline evaluation of initial configuration.",
                "param": "[Baseline]",
                "old_value": "N/A",
                "new_value": "N/A",
                "old_score": 0.0,
                "new_score": baseline_report.expected_term_pass_rate or 0.0,
                "accepted": 1,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "avg_latency_ms": baseline_report.avg_latency_ms,
                "total_tokens": baseline_report.total_tokens,
                "composite_score": baseline_report.composite_score,
                "experiment_id": experiment_id,
                "proposal_status": "baseline"
            })

        best_accepted_config = dict(baseline_config)
        best_accepted_report = baseline_report
        last_eval_results = baseline_dict["results"]

        # Initialize Optuna Study with SQLite persistence for study resumption and audit
        direction = objective_engine.direction
        optuna_db_url = f"sqlite:///{os.path.abspath(self.db_path)}"
        study = create_study(
            study_name=f"study_{experiment_id}",
            sampler_type=sampler_type,
            seed=seed,
            direction=direction,
            storage=optuna_db_url
        )

        # 2. Main Optimization Loop
        for trial_idx in range(1, trial_budget + 1):
            curr_iter_num = start_iter_num + trial_idx
            trial_id = f"trial_{experiment_id}_{trial_idx}"

            # Step A: Agent Diagnostic Reasoning
            failing = [r for r in last_eval_results if not r.get("passed", False)]
            diagnosis = self.diagnostician.diagnose_failures(
                failing_questions=failing,
                current_config=best_accepted_config,
                parameters_manifest=manifest.parameters,
                recent_history=[]
            )
            hypothesis = diagnosis.get("hypothesis", "Exploring parameter distribution.")
            suggested_bounds = diagnosis.get("suggested_bounds", {})

            # Step B: Optuna Parameter Exploration
            optuna_trial = study.ask()
            candidate_config = build_optuna_search_space(
                trial=optuna_trial,
                parameters=manifest.parameters,
                agent_suggested_bounds=suggested_bounds
            )

            # Step C: Pre-execution validation
            val_resp = self.adapter.validate_config(candidate_config)
            if not val_resp.valid:
                rejection_msg = f"Candidate validation failed: {'; '.join(val_resp.errors)}"
                db.log_iteration(
                    iter_num=curr_iter_num,
                    hypothesis=hypothesis,
                    param="invalid_config",
                    old_val="N/A",
                    new_val=str(candidate_config),
                    old_score=best_accepted_report.expected_term_pass_rate or 0.0,
                    new_score=best_accepted_report.expected_term_pass_rate or 0.0,
                    accepted=False,
                    motivated_by="",
                    avg_latency_ms=0.0,
                    total_tokens=0,
                    composite_score=best_accepted_report.composite_score,
                    project_id=project_id,
                    experiment_id=experiment_id,
                    trial_id=trial_id,
                    config_snapshot=candidate_config,
                    score_improvement=0.0,
                    rejection_reason=rejection_msg,
                    proposal_status="invalid_proposal",
                    db_path=self.db_path
                )
                continue

            # Step D: Apply configuration to target pipeline
            apply_res = self.adapter.apply_config(candidate_config)
            if not apply_res.success:
                rejection_msg = f"Failed to apply configuration: {apply_res.message}"
                self.adapter.restore_config(best_accepted_config)
                continue

            # Step E: Evaluate candidate with Phase 2 EvaluationService
            try:
                candidate_report = self.eval_service.evaluate_configuration(
                    config=candidate_config,
                    dataset_filename=dataset_filename,
                    role="tuning",
                    is_experimental=True,
                    adapter=self.adapter
                )
                cand_eval_dict = self.eval_service.to_legacy_eval_dict(candidate_report)
            except Exception as e:
                # Safe recovery on crash
                self.adapter.restore_config(best_accepted_config)
                db.log_iteration(
                    iter_num=curr_iter_num,
                    hypothesis=hypothesis,
                    param="crash",
                    old_val="N/A",
                    new_val=str(candidate_config),
                    old_score=best_accepted_report.expected_term_pass_rate or 0.0,
                    new_score=best_accepted_report.expected_term_pass_rate or 0.0,
                    accepted=False,
                    motivated_by="",
                    avg_latency_ms=0.0,
                    total_tokens=0,
                    composite_score=best_accepted_report.composite_score,
                    project_id=project_id,
                    experiment_id=experiment_id,
                    trial_id=trial_id,
                    config_snapshot=candidate_config,
                    score_improvement=0.0,
                    rejection_reason=f"Evaluation crash: {str(e)}",
                    proposal_status="evaluation_failed",
                    db_path=self.db_path
                )
                continue

            # Step F: Objective evaluation & Constraint satisfaction
            accepted, decision_reason, score_diff = objective_engine.evaluate_candidate(
                candidate_report=candidate_report,
                baseline_report=best_accepted_report
            )

            # Report outcome to Optuna for Bayesian tracking
            eval_metric_val = getattr(candidate_report, objective_engine.primary, candidate_report.composite_score)
            study.tell(optuna_trial, eval_metric_val)

            # Determine which parameter changed for logging
            diffs = self.promotion_manager.generate_config_diff(best_accepted_config, candidate_config)
            param_label = diffs[0]["parameter"] if len(diffs) == 1 else f"{len(diffs)} params"
            old_label = str(diffs[0]["old_value"]) if len(diffs) == 1 else "multi"
            new_label = str(diffs[0]["new_value"]) if len(diffs) == 1 else "multi"

            if accepted:
                best_accepted_config = dict(candidate_config)
                best_accepted_report = candidate_report
                last_eval_results = cand_eval_dict["results"]
            else:
                # CRITICAL SAFETY: Restore previous best configuration on rejected candidate
                self.adapter.restore_config(best_accepted_config)

            # Record iteration and question telemetry
            db.log_iteration(
                iter_num=curr_iter_num,
                hypothesis=hypothesis,
                param=param_label,
                old_val=old_label,
                new_val=new_label,
                old_score=best_accepted_report.expected_term_pass_rate or 0.0,
                new_score=candidate_report.expected_term_pass_rate or 0.0,
                accepted=accepted,
                motivated_by=diagnosis.get("reasoning", ""),
                avg_latency_ms=candidate_report.avg_latency_ms,
                total_tokens=candidate_report.total_tokens,
                composite_score=candidate_report.composite_score,
                project_id=project_id,
                experiment_id=experiment_id,
                trial_id=trial_id,
                config_snapshot=candidate_config,
                score_improvement=score_diff if accepted else 0.0,
                rejection_reason="" if accepted else decision_reason,
                proposal_status="success",
                db_path=self.db_path
            )

            if candidate_report.question_results:
                db.save_question_evaluations(
                    trial_id=trial_id,
                    experiment_id=experiment_id,
                    iteration_number=curr_iter_num,
                    question_results=candidate_report.question_results,
                    db_path=self.db_path
                )

            if on_iteration_callback:
                await on_iteration_callback({
                    "iteration_number": curr_iter_num,
                    "hypothesis": hypothesis,
                    "param": param_label,
                    "old_value": old_label,
                    "new_value": new_label,
                    "old_score": best_accepted_report.expected_term_pass_rate or 0.0,
                    "new_score": candidate_report.expected_term_pass_rate or 0.0,
                    "accepted": 1 if accepted else 0,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "avg_latency_ms": candidate_report.avg_latency_ms,
                    "total_tokens": candidate_report.total_tokens,
                    "composite_score": candidate_report.composite_score,
                    "experiment_id": experiment_id,
                    "rejection_reason": decision_reason if not accepted else ""
                })

        return {
            "experiment_id": experiment_id,
            "best_config": best_accepted_config,
            "best_report": best_accepted_report,
            "total_trials": trial_budget
        }

