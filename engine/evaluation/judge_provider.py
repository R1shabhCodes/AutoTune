"""
engine/evaluation/judge_provider.py
Semantic RAG Judge interface supporting local LLM evaluations (Ollama)
and optional cloud providers (Gemini / Ragas compatibility).
Computes Faithfulness, Answer Relevancy, Context Precision, and Context Recall.
Missing ground-truth references are handled transparently as None (not zero).
"""
import json
import re
import urllib.request
import os
import sys
from typing import Dict, Any, Optional, List, Tuple
from evaluation.base import EvalSample

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import models


class SemanticJudgeProvider:
    """
    Evaluates semantic quality of RAG generations using an LLM-as-a-Judge pattern.
    Default uses Ollama with the optimizer/judge model.
    """
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or models.get_optimizer_model()
        self.provider_version = "AutoTune-SemanticJudge/2.0"

    def evaluate_faithfulness(self, sample: EvalSample) -> Optional[float]:
        """
        Measures factual consistency of generated answer against retrieved contexts.
        Returns: Score between 0.0 and 1.0, or None if evaluation fails.
        """
        if not sample.retrieved_contexts or not sample.generated_answer.strip():
            return None

        context_str = "\n---\n".join(sample.retrieved_contexts)
        prompt = f"""You are an objective evaluation judge assessing RAG faithfulness.
Given the retrieved context and generated answer, determine whether every factual claim in the answer is directly supported by the context.

Context:
{context_str}

Generated Answer:
{sample.generated_answer}

Respond ONLY with a JSON object:
{{
  "verdict": "yes" | "partial" | "no",
  "score": <float between 0.0 and 1.0>,
  "reasoning": "<short explanation>"
}}"""
        return self._call_judge_score(prompt)

    def evaluate_answer_relevancy(self, sample: EvalSample) -> Optional[float]:
        """
        Measures how directly the answer addresses the question asked.
        """
        if not sample.generated_answer.strip():
            return 0.0

        prompt = f"""You are an objective evaluation judge assessing RAG answer relevancy.
Assess whether the generated answer directly answers the question without unnecessary fluff.

Question:
{sample.question}

Generated Answer:
{sample.generated_answer}

Respond ONLY with a JSON object:
{{
  "verdict": "relevant" | "partially_relevant" | "irrelevant",
  "score": <float between 0.0 and 1.0>,
  "reasoning": "<short explanation>"
}}"""
        return self._call_judge_score(prompt)

    def evaluate_context_precision(self, sample: EvalSample) -> Optional[float]:
        """
        Measures whether relevant context chunks are ranked higher than irrelevant ones.
        Requires reference_answer or expected_terms to verify relevance.
        """
        if not sample.retrieved_contexts:
            return None
        target = sample.reference_answer or " ".join(sample.expected_terms)
        if not target.strip():
            return None

        # Calculate rank precision of chunks containing key target elements
        target_words = set(re.findall(r'\w+', target.lower()))
        hits = []
        for ctx in sample.retrieved_contexts:
            ctx_words = set(re.findall(r'\w+', ctx.lower()))
            overlap = len(target_words.intersection(ctx_words)) / max(len(target_words), 1)
            hits.append(1.0 if overlap >= 0.3 else 0.0)

        # Average Precision at K
        precisions = []
        running_hits = 0
        for i, hit in enumerate(hits, start=1):
            if hit > 0:
                running_hits += 1
                precisions.append(running_hits / i)

        if not precisions:
            return 0.0
        return round(sum(precisions) / len(precisions), 4)

    def evaluate_context_recall(self, sample: EvalSample) -> Optional[float]:
        """
        Measures whether all facts in the reference answer can be attributed to the retrieved context.
        Strict requirement: Returns None if reference_contexts or reference_answer is missing.
        Do NOT report zero if reference data is absent.
        """
        if not sample.reference_answer and not sample.reference_contexts:
            return None  # Missing reference data -> Not evaluated, NOT zero.

        ref_text = sample.reference_answer or " ".join(sample.reference_contexts or [])
        retrieved_text = " ".join(sample.retrieved_contexts).lower()
        ref_words = set(re.findall(r'\w+', ref_text.lower()))
        if not ref_words:
            return None

        retrieved_words = set(re.findall(r'\w+', retrieved_text))
        recalled = len(ref_words.intersection(retrieved_words)) / len(ref_words)
        return round(recalled, 4)

    def _call_judge_score(self, prompt: str) -> Optional[float]:
        """Calls the configured LLM judge to extract score."""
        try:
            # Check Ollama availability first
            ollama_url = models.get_ollama_base_url()
            req_data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0}
            }
            req = urllib.request.Request(
                f"{ollama_url}/api/generate",
                data=json.dumps(req_data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10.0) as res:
                if res.status == 200:
                    data = json.loads(res.read().decode("utf-8"))
                    text = data.get("response", "")
                    parsed = json.loads(text)
                    score = float(parsed.get("score", 0.0))
                    return max(0.0, min(1.0, round(score, 4)))
        except Exception:
            # Gracefully handle network timeouts or disabled local judge
            pass
        return None

