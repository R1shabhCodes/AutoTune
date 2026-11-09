"""
engine/evaluation/deterministic_metrics.py
Deterministic metrics: exact matching, expected term containment,
numerical grounding, citation verification, and failure categorization.
"""
import re
from typing import List, Tuple, Dict, Any, Optional
from evaluation.base import EvalSample


def compute_expected_term_pass_rate(generated_answer: str, expected_terms: List[str]) -> Tuple[float, int, int]:
    """
    Computes pass rate for expected terms.
    Returns: (term_pass_rate, matched_count, total_expected)
    """
    if not expected_terms:
        return 1.0, 0, 0
    
    answer_lower = generated_answer.lower()
    matched = sum(1 for term in expected_terms if term.lower() in answer_lower)
    return round(matched / len(expected_terms), 4), matched, len(expected_terms)


def compute_exact_match(generated_answer: str, reference_answer: Optional[str]) -> float:
    """
    Computes strict normalized exact match between generated answer and reference answer.
    """
    if not reference_answer:
        return 0.0
    norm_gen = " ".join(re.findall(r'\w+', generated_answer.lower()))
    norm_ref = " ".join(re.findall(r'\w+', reference_answer.lower()))
    return 1.0 if norm_gen == norm_ref else 0.0


def verify_numerical_grounding(answer: str, contexts: List[str]) -> Tuple[bool, List[str]]:
    """
    Extracts numerical figures from answer and verifies presence in context chunks.
    Preserves comma formats, percentages, decimals.
    """
    # Regex to find numbers, currency values, percentages
    num_pattern = re.compile(r'\b(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?\b')
    answer_nums = set(num_pattern.findall(answer))
    
    if not answer_nums:
        return True, []
        
    combined_context = " ".join(contexts)
    context_nums = set(num_pattern.findall(combined_context))
    
    # Check each answer number
    ungrounded = []
    for num in answer_nums:
        clean_num = num.replace(",", "").replace("%", "")
        # Filter trivial small indices or years if present in answer formatting
        found = False
        if num in combined_context or clean_num in combined_context:
            found = True
        else:
            # Check without commas in context
            context_no_commas = combined_context.replace(",", "")
            if clean_num in context_no_commas:
                found = True
                
        if not found:
            ungrounded.append(num)
            
    return (len(ungrounded) == 0), sorted(ungrounded)


def verify_citation_coverage(answer: str) -> bool:
    """
    Checks whether the generated response contains structured citation markers.
    e.g., [Source: ...], [1], [doc.txt]
    """
    answer_lower = answer.lower()
    if "[source:" in answer_lower or "[source" in answer_lower:
        return True
    if re.search(r'\[\d+\]', answer):
        return True
    return False


def categorize_question_failure(
    sample: EvalSample,
    term_pass_rate: float,
    numerical_grounded: bool,
    citation_present: bool,
    is_error: bool
) -> Optional[str]:
    """
    Deterministically categorizes the failure reason when a response does not satisfy quality criteria.
    Categories:
    - 'infrastructure_error'
    - 'unanswerable_violation'
    - 'missing_context'
    - 'hallucination'
    - 'irrelevant_answer'
    - 'citation_failure'
    - 'latency_problem'
    - None (if passed)
    """
    if is_error or sample.is_error:
        return "infrastructure_error"
        
    # Unanswerable query handling: if question is unanswerable, answer should abstain
    if not sample.answerable:
        abstain_phrases = ["do not know", "cannot answer", "not mentioned", "not found in context", "not provided"]
        abstains = any(phrase in sample.generated_answer.lower() for phrase in abstain_phrases)
        if not abstains:
            return "unanswerable_violation"
        return None

    # Context retrieval failure: contexts empty or missing
    if not sample.retrieved_contexts:
        return "missing_context"

    # Numerical hallucination
    if not numerical_grounded:
        return "hallucination"

    # Term / Semantic mismatch
    if term_pass_rate < 1.0:
        # Check if expected terms were in the retrieved context
        context_text = " ".join(sample.retrieved_contexts).lower()
        terms_in_context = [term for term in sample.expected_terms if term.lower() in context_text]
        if len(terms_in_context) < len(sample.expected_terms):
            return "missing_context"
        else:
            return "irrelevant_answer"

    # Latency problem: if latency exceeds 60s
    if sample.latency_ms > 60000:
        return "latency_problem"

    return None

