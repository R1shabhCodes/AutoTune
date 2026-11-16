"""
engine/evaluation/objectives.py
Configurable optimization objectives and constraints.
Allows users to optimize for answer quality, retrieval quality, latency, tokens,
or balanced multi-objective goals with threshold constraints.
"""
from typing import Dict, Any, Tuple, Optional
from evaluation.base import AggregateEvaluationReport


class OptimizationObjective:
    """
    Evaluates whether an evaluation report meets configured objective targets and constraints.
    """
    DEFAULT_SPEC = {
        "primary": "composite_score",
        "direction": "maximize",
        "constraints": {
            "error_rate_max": 0.0,
            "numerical_grounding_min": 0.70
        }
    }

    def __init__(self, spec: Optional[Dict[str, Any]] = None):
        self.spec = spec or self.DEFAULT_SPEC
        self.primary = self.spec.get("primary", "composite_score")
        self.direction = self.spec.get("direction", "maximize")
        self.constraints = self.spec.get("constraints", {})

    def evaluate_candidate(
        self,
        candidate_report: AggregateEvaluationReport,
        baseline_report: Optional[AggregateEvaluationReport] = None
    ) -> Tuple[bool, str, float]:
        """
        Determines whether a candidate should be ACCEPTED based on objective and constraints.
        Returns: (accepted: bool, reason: str, score_diff: float)
        """
        # 1. Check constraints first
        for constraint_name, threshold in self.constraints.items():
            if constraint_name == "error_rate_max" and candidate_report.error_rate > threshold:
                return False, f"Constraint violated: error_rate ({candidate_report.error_rate}) exceeds max ({threshold}).", 0.0
            
            if constraint_name == "p95_latency_max_ms" and candidate_report.p95_latency_ms > threshold:
                return False, f"Constraint violated: p95_latency ({candidate_report.p95_latency_ms}ms) exceeds max ({threshold}ms).", 0.0
                
            if constraint_name == "max_tokens_per_query" and candidate_report.avg_tokens_per_query > threshold:
                return False, f"Constraint violated: avg_tokens ({candidate_report.avg_tokens_per_query}) exceeds max ({threshold}).", 0.0

            if constraint_name == "numerical_grounding_min":
                grounding = candidate_report.numerical_grounding_rate or 0.0
                if grounding < threshold:
                    return False, f"Constraint violated: numerical_grounding ({grounding}) below min ({threshold}).", 0.0

            if constraint_name == "faithfulness_min":
                if candidate_report.faithfulness is not None and candidate_report.faithfulness < threshold:
                    return False, f"Constraint violated: faithfulness ({candidate_report.faithfulness}) below min ({threshold}).", 0.0

        # Extract primary metric value
        cand_val = getattr(candidate_report, self.primary, None)
        if cand_val is None:
            # Fallback to composite score
            cand_val = candidate_report.composite_score

        if baseline_report is None:
            # Baseline evaluation always passes constraints check
            return True, "Baseline evaluation accepted as initial reference.", 0.0

        base_val = getattr(baseline_report, self.primary, None)
        if base_val is None:
            base_val = baseline_report.composite_score

        diff = round(cand_val - base_val, 4)

        if self.direction == "maximize":
            if cand_val > base_val:
                return True, f"Improvement achieved: {self.primary} increased from {base_val} to {cand_val} (+{diff}).", diff
            else:
                return False, f"Candidate {self.primary} ({cand_val}) did not improve upon best ({base_val}).", diff
        else:  # minimize (e.g., latency, tokens, cost)
            if cand_val < base_val:
                return True, f"Improvement achieved: {self.primary} decreased from {base_val} to {cand_val} ({diff}).", diff
            else:
                return False, f"Candidate {self.primary} ({cand_val}) did not decrease from best ({base_val}).", diff

