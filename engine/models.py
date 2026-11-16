# models.py
# Provider health checks, model availability discovery, and multi-model configuration for AutoTune.

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_env_variable(var_name: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieves an environment variable, checking os.environ first then local engine/.env."""
    val = os.environ.get(var_name)
    if val:
        return val

    env_paths = [
        os.path.join(ENGINE_DIR, ".env"),
        os.path.join(os.path.dirname(ENGINE_DIR), ".env")
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == var_name:
                                return v.strip().strip('"').strip("'")
            except Exception:
                pass
    return default

def get_ollama_base_url() -> str:
    """Returns the base URL for the Ollama daemon."""
    return get_env_variable("OLLAMA_URL", "http://localhost:11434").rstrip("/")

def get_optimizer_model() -> str:
    """
    Returns the active optimizer LLM model.
    Defaults to qwen2.5:1.5b.
    Can be configured via OPTIMIZER_MODEL.
    """
    return get_env_variable("OPTIMIZER_MODEL", "qwen2.5:1.5b")

def get_generator_model() -> str:
    """
    Returns the active RAG generator LLM model.
    Defaults to llama3.2:latest.
    Can be configured via GENERATOR_MODEL.
    """
    return get_env_variable("GENERATOR_MODEL", "llama3.2:latest")

def check_ollama_health(timeout: float = 3.0) -> Tuple[bool, str, List[str]]:
    """
    Performs a health check on the Ollama daemon and lists available models.
    Returns: (is_healthy, status_message, list_of_model_names)
    """
    base_url = get_ollama_base_url()
    tags_url = f"{base_url}/api/tags"

    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "AutoTune/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                return True, f"Ollama is online at {base_url}", models
            return False, f"Ollama returned HTTP status {res.status}", []
    except urllib.error.URLError as e:
        if "10061" in str(e) or "refused" in str(e).lower():
            return False, f"Ollama connection refused at {base_url}. Ensure the Ollama daemon is running.", []
        return False, f"Ollama connection error: {str(e)}", []
    except Exception as e:
        return False, f"Ollama health check error: {str(e)}", []

def check_model_availability(model_name: str, available_models: Optional[List[str]] = None) -> Tuple[bool, str]:
    """
    Checks if a required model is available on Ollama.
    """
    if available_models is None:
        healthy, _, available_models = check_ollama_health()
        if not healthy:
            return False, "Ollama daemon unreachable."

    # Direct match or prefix match (e.g., 'llama3.2:latest' matching 'llama3.2')
    for m in available_models:
        if m == model_name or m.split(":")[0] == model_name.split(":")[0]:
            return True, f"Model '{model_name}' is available ({m})."

    return False, f"Model '{model_name}' is not found in Ollama. Available: {available_models}"

def validate_provider_setup() -> Dict[str, Any]:
    """
    Validates availability of both optimizer and generator models before starting an optimization run.
    """
    gemini_key = get_env_variable("GEMINI_API_KEY")
    opt_model = get_optimizer_model()
    gen_model = get_generator_model()

    status = {
        "gemini_available": bool(gemini_key),
        "ollama_available": False,
        "optimizer_model": opt_model,
        "generator_model": gen_model,
        "optimizer_ready": False,
        "generator_ready": False,
        "available_ollama_models": [],
        "warnings": [],
        "errors": []
    }

    ollama_ok, msg, models = check_ollama_health()
    status["ollama_available"] = ollama_ok
    status["available_ollama_models"] = models

    if not ollama_ok:
        if gemini_key:
            status["warnings"].append(f"{msg}. Falling back to Gemini API.")
            status["optimizer_ready"] = True
            status["generator_ready"] = True
        else:
            status["errors"].append(msg)
            return status
    else:
        # Check optimizer model availability
        opt_ok, opt_msg = check_model_availability(opt_model, models)
        status["optimizer_ready"] = opt_ok
        if not opt_ok:
            status["errors"].append(opt_msg)

        # Check generator model availability
        gen_ok, gen_msg = check_model_availability(gen_model, models)
        status["generator_ready"] = gen_ok
        if not gen_ok:
            status["errors"].append(gen_msg)

    return status

