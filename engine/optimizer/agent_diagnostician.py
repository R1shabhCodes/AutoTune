"""
engine/optimizer/agent_diagnostician.py
LLM-based diagnostic reasoning for AutoTune 2.0.
Analyzes failing questions, isolates retrieval vs generation vs grounding errors,
and generates structured hypotheses and suggested parameter search ranges for Optuna.
Uses Qwen 2.5 1.5B via Ollama.
"""
import json
from typing import Dict, Any, List, Optional
import models


class AgentDiagnostician:
    """
    Agentic diagnostician that analyzes benchmark question failures to formulate optimization hypotheses.
    """
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or models.get_optimizer_model()

    def diagnose_failures(
        self,
        failing_questions: List[Dict[str, Any]],
        current_config: Dict[str, Any],
        parameters_manifest: Dict[str, Any],
        recent_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyzes failure distribution and returns hypothesis, suggested focus parameters, and bounds.
        """
        if not failing_questions:
            return {
                "hypothesis": "All questions passed in the baseline evaluation. Exploring parameter boundaries for latency and token efficiency.",
                "focus_parameters": list(parameters_manifest.keys())[:2],
                "reasoning": "Baseline achieved complete question pass rate; optimizing secondary objectives (latency, tokens).",
                "suggested_bounds": {}
            }

        # Summarize failures
        failure_summaries = []
        for q in failing_questions[:4]:
            failure_summaries.append({
                "question": q.get("question", "")[:120],
                "failure_category": q.get("failure_category", "unknown"),
                "expected": q.get("expected_terms", []) or q.get("expected", []),
                "actual_snippet": (q.get("generated_answer", "") or "")[:100],
                "grounding_passed": q.get("grounding_passed", True)
            })

        param_summary = {}
        for k, v in parameters_manifest.items():
            param_summary[k] = {
                "type": getattr(v, "type", "string"),
                "min": getattr(v, "min", None),
                "max": getattr(v, "max", None),
                "options": getattr(v, "options", None),
                "current": current_config.get(k)
            }

        prompt = f"""You are an expert RAG diagnostic optimizer.
Analyze these benchmark question failures and the application's available parameters.

CURRENT CONFIGURATION:
{json.dumps(current_config, indent=2)}

AVAILABLE PARAMETERS:
{json.dumps(param_summary, indent=2)}

SAMPLE FAILING QUESTIONS:
{json.dumps(failure_summaries, indent=2)}

RECENT EXPERIMENT HISTORY:
{json.dumps(recent_history[:3], indent=2)}

DIAGNOSTIC TASK:
1. Identify the root weakness (e.g. context retrieval chunking, top_k ranking, or generation temperature).
2. Propose a clear hypothesis explaining what parameter adjustments should be explored.
3. Suggest 1 or 2 focus parameters and recommended exploration bounds.

Respond ONLY with a JSON object in this exact schema:
{{
  "hypothesis": "<1-2 sentence testable optimization hypothesis>",
  "focus_parameters": ["<param1>", "<param2>"],
  "reasoning": "<concise explanation of retrieval or generation weakness>",
  "suggested_bounds": {{
    "<param1>": {{"min": <number>, "max": <number>}}
  }}
}}"""

        try:
            raw_res = models.call_ollama_json(self.model_name, prompt, timeout=25.0)
            parsed = json.loads(raw_res) if isinstance(raw_res, str) else raw_res
            if isinstance(parsed, dict) and "hypothesis" in parsed:
                return parsed
        except Exception:
            pass

        # Robust deterministic fallback if LLM times out or is offline
        focus = ["chunk_size", "top_k"] if "chunk_size" in parameters_manifest else list(parameters_manifest.keys())[:2]
        return {
            "hypothesis": "Context retrieval coverage is insufficient for multi-clause questions; expanding context window and candidate search.",
            "focus_parameters": focus,
            "reasoning": "Observed context mismatch or generation divergence on benchmark questions.",
            "suggested_bounds": {}
        }

