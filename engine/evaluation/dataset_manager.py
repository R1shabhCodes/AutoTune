"""
engine/evaluation/dataset_manager.py
Standard dataset schema, loading, role separation, and immutability validation.
Roles:
1. 'tuning' (optimizer may inspect results and failing questions)
2. 'validation' (used for candidate selection)
3. 'holdout' (blind, strictly isolated, evaluated only on final candidate)
4. 'regression' (prevents degradation of critical past queries)
"""
import os
import json
import hashlib
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DatasetItemSchema(BaseModel):
    id: str = Field(default="")
    question: str
    reference_answer: Optional[str] = None
    reference_contexts: Optional[List[str]] = None
    expected_answer_contains: List[str] = Field(default_factory=list)
    expected_claims: List[str] = Field(default_factory=list)
    answerable: bool = True
    category: str = "general"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DatasetManager:
    """
    Manages dataset loading, role separation, versioning, and validation.
    """
    ALLOWED_ROLES = {"tuning", "validation", "holdout", "regression"}

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def load_dataset(self, filename: str, role: str = "tuning") -> List[Dict[str, Any]]:
        """
        Loads and standardizes a dataset file.
        Accepts legacy formats with 'expected' or 'expected_answer_contains'.
        """
        if role not in self.ALLOWED_ROLES:
            raise ValueError(f"Invalid dataset role '{role}'. Must be one of {self.ALLOWED_ROLES}")

        file_path = os.path.join(self.base_dir, filename) if not os.path.isabs(filename) else filename
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file does not exist: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError("Dataset JSON must contain an array of question items.")

        standardized = []
        for idx, item in enumerate(raw_data):
            q_id = item.get("id", f"q_{role}_{idx+1:03d}")
            question = item.get("question", "").strip()
            if not question:
                continue

            expected = item.get("expected_answer_contains", item.get("expected", []))
            if isinstance(expected, str):
                expected = [expected]

            claims = item.get("expected_claims", [])
            ref_ans = item.get("reference_answer", None)
            ref_ctx = item.get("reference_contexts", None)
            answerable = item.get("answerable", True)
            category = item.get("category", "finance")

            standardized.append({
                "id": q_id,
                "question": question,
                "reference_answer": ref_ans,
                "reference_contexts": ref_ctx,
                "expected_answer_contains": expected,
                "expected": expected,  # legacy compatibility
                "expected_claims": claims,
                "answerable": answerable,
                "category": category,
                "role": role,
                "dataset_file": os.path.basename(file_path)
            })

        return standardized

    def compute_dataset_hash(self, dataset: List[Dict[str, Any]]) -> str:
        """Computes deterministic SHA-256 hash for dataset immutability."""
        content = json.dumps(dataset, sort_keys=True)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def validate_holdout_isolation(self, tuning_data: List[Dict[str, Any]], holdout_data: List[Dict[str, Any]]) -> bool:
        """
        Verifies that no question from the blind holdout dataset leaks into the tuning dataset.
        """
        tuning_questions = {d["question"].strip().lower() for d in tuning_data}
        for h in holdout_data:
            if h["question"].strip().lower() in tuning_questions:
                return False  # Leak detected!
        return True

