# config_validator.py
# Formal validation, schema enforcement, and immutable snapshot management for RAG configurations.

import json
import hashlib
from typing import Tuple, Dict, Any, Optional

PARAM_SPECS = {
    "chunk_size": {
        "type": int,
        "min": 50,
        "max": 3000,
        "description": "Character size of document chunks"
    },
    "chunk_overlap": {
        "type": int,
        "min": 0,
        "max": 1000,
        "description": "Character overlap between consecutive chunks"
    },
    "top_k": {
        "type": int,
        "min": 1,
        "max": 30,
        "description": "Number of retrieved context chunks"
    },
    "temperature": {
        "type": float,
        "min": 0.0,
        "max": 2.0,
        "description": "LLM generation temperature"
    },
    "retrieval_strategy": {
        "type": str,
        "options": ["vector", "keyword", "hybrid"],
        "description": "Information retrieval algorithm"
    },
    "prompt_template": {
        "type": str,
        "required_placeholders": ["{context}", "{question}"],
        "description": "Prompt template containing {context} and {question}"
    }
}

REQUIRED_PARAMS = ["chunk_size", "chunk_overlap", "top_k", "temperature"]

def clean_param_value(param: str, raw_value: Any) -> Tuple[bool, Optional[Any], str]:
    """
    Validates and cleans a proposed parameter value according to PARAM_SPECS.
    Returns: (is_valid, cleaned_value, error_reason)
    """
    if param not in PARAM_SPECS:
        return False, None, f"Unknown parameter '{param}'. Supported knobs: {list(PARAM_SPECS.keys())}"

    spec = PARAM_SPECS[param]
    expected_type = spec["type"]

    # 1. Type coercion and validation
    try:
        if expected_type is int:
            cleaned = int(float(raw_value))
        elif expected_type is float:
            cleaned = float(raw_value)
        elif expected_type is str:
            cleaned = str(raw_value).strip()
        else:
            cleaned = raw_value
    except (ValueError, TypeError) as e:
        return False, None, f"Invalid value '{raw_value}' for '{param}': expected {expected_type.__name__}"

    # 2. Boundary and option checks
    if "min" in spec and cleaned < spec["min"]:
        return False, None, f"Parameter '{param}' value {cleaned} is below minimum allowed ({spec['min']})"
    if "max" in spec and cleaned > spec["max"]:
        return False, None, f"Parameter '{param}' value {cleaned} exceeds maximum allowed ({spec['max']})"

    if "options" in spec:
        cleaned_opt = cleaned.lower()
        if cleaned_opt not in spec["options"]:
            return False, None, f"Invalid option '{cleaned}' for '{param}'. Must be one of: {spec['options']}"
        cleaned = cleaned_opt

    if "required_placeholders" in spec:
        for placeholder in spec["required_placeholders"]:
            if placeholder not in cleaned:
                return False, None, f"Template for '{param}' is missing required placeholder '{placeholder}'"

    return True, cleaned, ""

def validate_config(config_dict: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates a complete RAG configuration dictionary and enforces cross-parameter constraints.
    Returns: (is_valid, error_reason, cleaned_config)
    """
    if not isinstance(config_dict, dict):
        return False, "Configuration must be a dictionary", {}

    cleaned_config = {}

    # Check required parameters
    for req in REQUIRED_PARAMS:
        if req not in config_dict:
            return False, f"Missing required parameter '{req}'", {}

    # Validate each parameter
    for k, v in config_dict.items():
        if k in PARAM_SPECS:
            valid, cleaned_v, err = clean_param_value(k, v)
            if not valid:
                return False, err, {}
            cleaned_config[k] = cleaned_v
        else:
            cleaned_config[k] = v

    # Enforce cross-parameter dependencies
    chunk_size = cleaned_config.get("chunk_size", 200)
    chunk_overlap = cleaned_config.get("chunk_overlap", 20)

    if chunk_overlap >= chunk_size:
        return False, f"Constraint violation: chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})", {}

    return True, "", cleaned_config

def validate_proposal(current_config: Dict[str, Any], param: str, raw_new_value: Any) -> Tuple[bool, str, Any, Optional[Dict[str, Any]]]:
    """
    Validates a proposed parameter modification against the current configuration.
    Returns: (is_valid, error_reason, cleaned_value, candidate_config)
    """
    valid, cleaned_val, err = clean_param_value(param, raw_new_value)
    if not valid:
        return False, err, None, None

    candidate_config = current_config.copy()
    candidate_config[param] = cleaned_val

    is_valid, const_err, final_config = validate_config(candidate_config)
    if not is_valid:
        return False, const_err, None, None

    return True, "", cleaned_val, final_config

def create_config_snapshot(config_dict: Dict[str, Any], db_path: Optional[str] = None) -> Tuple[str, str]:
    """
    Generates a deterministic SHA256 snapshot ID and canonical JSON representation of a config.
    Optionally registers the snapshot into the database.
    Returns: (snapshot_id, canonical_json)
    """
    canonical_json = json.dumps(config_dict, sort_keys=True)
    config_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    snapshot_id = f"snap_{config_hash[:12]}"

    if db_path:
        try:
            import db
            conn = db.get_connection(db_path)
            cursor = conn.cursor()
            with conn:
                cursor.execute("""
                    INSERT OR IGNORE INTO config_snapshots (snapshot_id, config_hash, config_json, created_at)
                    VALUES (?, ?, ?, datetime('now'))
                """, (snapshot_id, config_hash, canonical_json))
            conn.close()
        except Exception:
            pass

    return snapshot_id, canonical_json

