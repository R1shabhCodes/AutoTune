# agent_loop.py
# Core optimization loop that proposes config changes, evaluates them, and logs results.
# Refactored in AutoTune 2.0 with formal state management, strict baseline preservation,
# immutable configuration snapshots, and isolated experimental executions.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import sqlite3
import datetime
import importlib
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

import config
import eval_harness
import rag_pipeline
import config_validator
import db

engine_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(engine_dir, "autotune.db")

# Multi-objective optimization weights (preserved from v1)
W_ACCURACY = 0.7
W_LATENCY = 0.2
W_TOKENS = 0.1
LATENCY_BUDGET_MS = 5000.0  # 5 seconds budget per question
TOKEN_BUDGET = 2000         # token budget per question

def compute_composite_score(
    accuracy: float,
    avg_latency_ms: float,
    total_tokens: int,
    num_questions: int,
    grounding_rate: float = 1.0
) -> float:
    """Computes a weighted composite score from accuracy, latency, and token usage, penalized by grounding failures."""
    latency_score = max(0.0, 1.0 - avg_latency_ms / LATENCY_BUDGET_MS)
    avg_tokens = total_tokens / max(num_questions, 1)
    token_score = max(0.0, 1.0 - avg_tokens / TOKEN_BUDGET)
    
    base_score = W_ACCURACY * accuracy + W_LATENCY * latency_score + W_TOKENS * token_score
    grounding_penalty = 0.3 * (1.0 - grounding_rate)
    
    return round(max(0.0, base_score - grounding_penalty), 4)

def init_db(db_path: str = DB_PATH):
    """Initializes the database schema using versioned, reversible migrations."""
    db.apply_migrations(db_path)

def log_iteration(
    iter_num: int,
    hypothesis: str,
    param: str,
    old_val: Any,
    new_val: Any,
    old_score: float,
    new_score: float,
    accepted: bool,
    motivated_by: str = "",
    avg_latency_ms: float = 0.0,
    total_tokens: int = 0,
    composite_score: float = 0.0,
    project_id: str = "default",
    experiment_id: str = "exp_legacy",
    trial_id: Optional[str] = None,
    dataset_id: str = "eval_set_tuning",
    config_snapshot: Optional[Dict[str, Any]] = None,
    score_improvement: float = 0.0,
    rejection_reason: str = "",
    proposal_status: str = "success",
    db_path: str = DB_PATH
):
    """Inserts an iteration record into the SQLite database with full state tracking."""
    snapshot_id = None
    if config_snapshot:
        snapshot_id, _ = config_validator.create_config_snapshot(config_snapshot, db_path=db_path)

    db.log_trial_record(
        iter_num=iter_num,
        hypothesis=hypothesis,
        param=param,
        old_val=old_val,
        new_val=new_val,
        old_score=old_score,
        new_score=new_score,
        accepted=accepted,
        motivated_by=motivated_by,
        avg_latency_ms=avg_latency_ms,
        total_tokens=total_tokens,
        composite_score=composite_score,
        project_id=project_id,
        experiment_id=experiment_id,
        trial_id=trial_id,
        dataset_id=dataset_id,
        config_snapshot_id=snapshot_id,
        config_snapshot=config_snapshot,
        score_improvement=score_improvement,
        rejection_reason=rejection_reason,
        proposal_status=proposal_status,
        db_path=db_path
    )

def get_history(limit: int = 10, experiment_id: Optional[str] = None, db_path: str = DB_PATH) -> list:
    """Retrieves the last N evaluation iterations from the SQLite database."""
    conn = db.get_connection(db_path)
    cursor = conn.cursor()
    try:
        if experiment_id:
            cursor.execute("""
                SELECT iteration_number, hypothesis, param, old_value, new_value, old_score, new_score, accepted,
                       motivated_by, avg_latency_ms, total_tokens, composite_score, project_id, experiment_id,
                       trial_id, config_snapshot, score_improvement, rejection_reason, proposal_status, timestamp
                FROM iterations
                WHERE experiment_id = ?
                ORDER BY iteration_number DESC
                LIMIT ?
            """, (experiment_id, limit))
        else:
            cursor.execute("""
                SELECT iteration_number, hypothesis, param, old_value, new_value, old_score, new_score, accepted,
                       motivated_by, avg_latency_ms, total_tokens, composite_score, project_id, experiment_id,
                       trial_id, config_snapshot, score_improvement, rejection_reason, proposal_status, timestamp
                FROM iterations
                ORDER BY iteration_number DESC
                LIMIT ?
            """, (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()

def save_config(new_config: dict):
    """Saves the configuration dictionary back to config.py and syncs it with apps/rag_finance/config.json."""
    content = f"""# config.py
# Current configuration for AutoTune RAG pipeline
# This file is programmatically read and updated by agent_loop.py

CONFIG = {repr(new_config)}
"""
    config_path = os.path.join(engine_dir, "config.py")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Sync to apps/rag_finance/config.json
    target_config_path = os.path.abspath(os.path.join(engine_dir, "..", "apps", "rag_finance", "config.json"))
    if os.path.exists(os.path.dirname(target_config_path)):
        try:
            with open(target_config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=2)
            print(f"Synced best config to target app at {target_config_path}")
        except Exception as e:
            print(f"Failed to sync config to target app: {e}")

def call_llm_json(prompt: str, system_prompt: str, model_override: Optional[str] = None) -> tuple:
    """
    Calls the LLM (Gemini or Ollama) requesting JSON output.
    Defaults to qwen2.5:1.5b via Ollama, or Gemini API if GEMINI_API_KEY is present.
    Supports model_override to test alternative models (e.g. glm-5.2:cloud).
    Returns: (parsed_dict_or_None, error_info_dict_or_None)
    """
    import models as model_provider

    gemini_key = model_provider.get_env_variable("GEMINI_API_KEY")

    if gemini_key:
        provider = "gemini"
        model = model_override or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": 0.5,
                "responseMimeType": "application/json"
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                resp = json.loads(res.read().decode("utf-8"))
                text = resp["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text), None
        except Exception as e:
            cat = "auth_error" if "401" in str(e) or "403" in str(e) else "api_error"
            err_info = {
                "provider": provider,
                "model": model,
                "category": cat,
                "exception_type": type(e).__name__,
                "message": str(e)
            }
            print(f"Gemini proposal generation error [{cat}]: {e}")
            return None, err_info
    else:
        provider = "ollama"
        ollama_url = model_provider.get_ollama_base_url()
        url = f"{ollama_url}/api/generate"
        model = model_override or model_provider.get_optimizer_model()

        payload = {
            "model": model,
            "prompt": f"System Instruction: {system_prompt}\n\nUser Prompt: {prompt}",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.5
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                resp = json.loads(res.read().decode("utf-8"))
                text = resp.get("response", "")
                return json.loads(text), None
        except Exception as e:
            cat = "connection_refused" if "10061" in str(e) or "refused" in str(e).lower() else "timeout" if "timeout" in str(e).lower() else "runtime_error"
            msg = f"Cannot connect to Ollama at {ollama_url}. Is Ollama running or should GEMINI_API_KEY be set?" if cat == "connection_refused" else str(e)
            err_info = {
                "provider": provider,
                "model": model,
                "category": cat,
                "exception_type": type(e).__name__,
                "message": msg
            }
            print(f"Ollama proposal generation error [{cat}]: {msg}")
            return None, err_info

def generate_proposal(current_config: dict, history: list, last_eval_results: list = None, model_override: Optional[str] = None) -> tuple:
    """
    Uses LLM to generate a single-parameter tuning proposal.
    Returns: (proposal_dict_or_None, error_info_or_None)
    Never returns arbitrary top_k fallback.
    """
    program_path = os.path.join(engine_dir, "program.md")
    with open(program_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    prompt = f"Here is the CURRENT BASELINE config of the RAG system:\n"
    prompt += json.dumps(current_config, indent=2) + "\n\n"
    
    if last_eval_results:
        failing_questions = [r for r in last_eval_results if not r.get("passed", False)]
        if failing_questions:
            prompt += "Here are some of the FAILING questions from the current configuration:\n"
            for idx, f in enumerate(failing_questions[:3]):
                prompt += f"Failure {idx+1}:\n"
                prompt += f"  - Question: {f['question']}\n"
                prompt += f"  - Expected keywords: {f['expected']}\n"
                prompt += f"  - RAG actual answer: {f['actual_answer']}\n\n"
    
    if history:
        prompt += "Here is the HISTORY of previous trials:\n"
        for h in history:
            prompt += f"- Iteration {h['iteration_number']}: changed '{h['param']}' ({h['old_value']} -> {h['new_value']}). Score: {h['old_score']:.4f} -> {h['new_score']:.4f} | Accepted: {bool(h['accepted'])}\n"
        prompt += "\n"
    else:
        prompt += "No iterations have been run yet.\n\n"
        
    prompt += "Propose one single parameter modification. Return valid JSON only, adhering to the required schema."

    last_error_info = None
    for attempt in range(3):
        try:
            proposal, err_info = call_llm_json(prompt, system_prompt, model_override=model_override)
            if isinstance(proposal, dict) and "param" in proposal and "new_value" in proposal:
                return proposal, None
            if err_info:
                last_error_info = err_info
        except Exception as e:
            last_error_info = {"category": "unexpected", "message": str(e)}

    print("Warning: LLM failed to generate a valid proposal after 3 attempts.")
    return None, last_error_info

async def run_optimization(
    num_iterations: int,
    on_iteration_callback=None,
    experiment_id: Optional[str] = None,
    project_id: str = "default",
    db_path: str = DB_PATH
):
    """
    Main optimization loop coordinating hypothesis generation, isolated evaluation,
    strict baseline tracking, immutable snapshot logging, and real-time streaming.
    """
    import models as model_provider

    init_db(db_path)

    # Pre-flight provider health and model availability check
    provider_status = model_provider.validate_provider_setup()
    if provider_status.get("errors"):
        err_text = "; ".join(provider_status["errors"])
        raise RuntimeError(f"Provider health check failed before experiment startup: {err_text}")

    print(f"Provider health check passed: Optimizer='{provider_status['optimizer_model']}' | Generator='{provider_status['generator_model']}'")

    # 1. Setup experiment ID
    if not experiment_id:
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_id = f"exp_{timestamp_str}"

    print(f"\n=======================================================")
    print(f"  Starting AutoTune Optimization: {experiment_id}")
    print(f"  Target Iterations: {num_iterations} | Project: {project_id}")
    print(f"=======================================================\n")

    importlib.reload(config)
    active_config = config.CONFIG.copy()

    # Validate active initial config
    is_valid, err, cleaned_active = config_validator.validate_config(active_config)
    if not is_valid:
        raise ValueError(f"Active configuration in config.py is invalid: {err}")
    active_config = cleaned_active

    # Check if this experiment already has iterations
    conn = db.get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM iterations WHERE experiment_id = ?", (experiment_id,))
    exp_trial_count = cursor.fetchone()[0]

    # Find the global max iteration number to preserve monotonic iteration_number
    cursor.execute("SELECT MAX(iteration_number) FROM iterations")
    max_global_iter = cursor.fetchone()[0] or 0
    conn.close()

    last_eval_results = []
    
    # Baseline setup: If new experiment, evaluate iteration 0 as baseline
    if exp_trial_count == 0:
        baseline_iter_num = max_global_iter + 1 if max_global_iter > 0 else 0
        print(f"--- Running Baseline Evaluation (Iteration {baseline_iter_num}) for {experiment_id} ---")
        
        baseline_res = eval_harness.evaluate_config(active_config, is_experimental=False)
        is_infra_err = baseline_res.get("is_infrastructure_error", False)
        infra_info = baseline_res.get("infrastructure_error_info")

        baseline_score = baseline_res["aggregate_score"]
        baseline_latency = baseline_res.get("avg_latency_ms", 0.0)
        baseline_tokens = baseline_res.get("total_tokens", 0)
        baseline_num_q = len(baseline_res.get("results", []))
        baseline_grounding = baseline_res.get("grounding_rate", 1.0)
        baseline_composite = compute_composite_score(baseline_score, baseline_latency, baseline_tokens, baseline_num_q, baseline_grounding)
        last_eval_results = baseline_res["results"]

        baseline_status = "infrastructure_error" if is_infra_err else "baseline"
        baseline_rejection = f"LLM Provider Offline [{infra_info['provider']}]: {infra_info['message']}" if is_infra_err and infra_info else ""
        baseline_hyp = "Baseline evaluation failed: LLM provider unreachable." if is_infra_err else "Baseline evaluation of initial configuration."

        log_iteration(
            iter_num=baseline_iter_num,
            hypothesis=baseline_hyp,
            param="[Baseline]",
            old_val="N/A",
            new_val="N/A",
            old_score=0.0,
            new_score=baseline_score,
            accepted=not is_infra_err,
            motivated_by="",
            avg_latency_ms=baseline_latency,
            total_tokens=baseline_tokens,
            composite_score=baseline_composite,
            project_id=project_id,
            experiment_id=experiment_id,
            trial_id=f"trial_{experiment_id}_0",
            config_snapshot=active_config,
            score_improvement=0.0,
            rejection_reason=baseline_rejection,
            proposal_status=baseline_status,
            db_path=db_path
        )

        # Save granular question evaluations for baseline
        if baseline_res.get("results"):
            db.save_question_evaluations(
                trial_id=f"trial_{experiment_id}_0",
                experiment_id=experiment_id,
                iteration_number=baseline_iter_num,
                question_results=baseline_res["results"],
                db_path=db_path
            )

        best_accepted_config = active_config.copy()
        best_accepted_score = baseline_score
        best_accepted_composite = baseline_composite
        start_iter = baseline_iter_num + 1

        if on_iteration_callback:
            await on_iteration_callback({
                "iteration_number": baseline_iter_num,
                "hypothesis": baseline_hyp,
                "param": "[Baseline]",
                "old_value": "N/A",
                "new_value": "N/A",
                "old_score": 0.0,
                "new_score": baseline_score,
                "accepted": 1 if not is_infra_err else 0,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "motivated_by": "",
                "avg_latency_ms": baseline_latency,
                "total_tokens": baseline_tokens,
                "composite_score": baseline_composite,
                "project_id": project_id,
                "experiment_id": experiment_id,
                "score_improvement": 0.0,
                "rejection_reason": baseline_rejection,
                "proposal_status": baseline_status
            })
    else:
        # Load best accepted candidate specifically for this experiment
        best_trial = db.get_experiment_best(experiment_id=experiment_id, db_path=db_path)
        if best_trial:
            best_accepted_score = best_trial["new_score"]
            best_accepted_composite = best_trial["composite_score"] if best_trial["composite_score"] is not None else best_accepted_score
            if best_trial.get("config_snapshot"):
                try:
                    best_accepted_config = json.loads(best_trial["config_snapshot"])
                except Exception:
                    best_accepted_config = active_config.copy()
            else:
                best_accepted_config = active_config.copy()
        else:
            best_accepted_config = active_config.copy()
            best_accepted_score = 0.0
            best_accepted_composite = 0.0

        start_iter = max_global_iter + 1

    # Run optimization iterations
    for i in range(start_iter, start_iter + num_iterations):
        print(f"\n--- Starting Trial {i} (Experiment: {experiment_id} | Best Composite: {best_accepted_composite:.4f}) ---")

        # 1. Fetch recent history for this experiment
        history = get_history(limit=10, experiment_id=experiment_id, db_path=db_path)

        # 2. Rate limit pause if using Gemini
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            import time
            time.sleep(4.0)

        # 3. Extract failing questions for context
        motivated_by_str = ""
        if last_eval_results:
            failing_qs = [r for r in last_eval_results if not r.get("passed", False)]
            if failing_qs:
                motivated_by_str = " | ".join([f["question"] for f in failing_qs[:3]])

        # 4. Generate proposal from the BEST ACCEPTED config (not a rejected config)
        proposal, prop_err = generate_proposal(best_accepted_config, history, last_eval_results)
        
        # Handle failed proposal explicitly
        if proposal is None:
            prov = prop_err.get("provider", "LLM") if prop_err else "LLM"
            cat = prop_err.get("category", "error") if prop_err else "failure"
            msg = prop_err.get("message", "LLM failed to generate a valid proposal after 3 attempts.") if prop_err else "LLM failed to generate a valid proposal after 3 attempts."
            rejection_msg = f"Proposal Unavailable [{prov}:{cat}] - {msg}"
            print(f"Trial {i} FAILED: {rejection_msg}")
            log_iteration(
                iter_num=i,
                hypothesis="Proposal generation failed.",
                param="[Unavailable]",
                old_val="N/A",
                new_val="N/A",
                old_score=best_accepted_score,
                new_score=best_accepted_score,
                accepted=False,
                motivated_by=motivated_by_str,
                avg_latency_ms=0.0,
                total_tokens=0,
                composite_score=best_accepted_composite,
                project_id=project_id,
                experiment_id=experiment_id,
                trial_id=f"trial_{experiment_id}_{i}",
                config_snapshot=best_accepted_config,
                score_improvement=0.0,
                rejection_reason=rejection_msg,
                proposal_status="failed_proposal",
                db_path=db_path
            )
            if on_iteration_callback:
                await on_iteration_callback({
                    "iteration_number": i,
                    "hypothesis": "Proposal generation failed.",
                    "param": "[Unavailable]",
                    "old_value": "N/A",
                    "new_value": "N/A",
                    "old_score": best_accepted_score,
                    "new_score": best_accepted_score,
                    "accepted": 0,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "motivated_by": motivated_by_str,
                    "avg_latency_ms": 0.0,
                    "total_tokens": 0,
                    "composite_score": best_accepted_composite,
                    "rejection_reason": rejection_msg,
                    "proposal_status": "failed_proposal"
                })
            continue

        param = proposal.get("param")
        hypothesis = proposal.get("hypothesis", "No hypothesis provided.")
        raw_new_val = proposal.get("new_value")
        old_val = best_accepted_config.get(param, "N/A")

        # 5. Formal validation layer
        is_valid, validation_err, cleaned_val, candidate_config = config_validator.validate_proposal(
            best_accepted_config, param, raw_new_val
        )

        if not is_valid:
            rejection_msg = f"Proposal validation failed: {validation_err}"
            print(f"Trial {i} REJECTED before evaluation: {rejection_msg}")
            log_iteration(
                iter_num=i,
                hypothesis=hypothesis,
                param=param or "None",
                old_val=old_val,
                new_val=str(raw_new_val),
                old_score=best_accepted_score,
                new_score=best_accepted_score,
                accepted=False,
                motivated_by=motivated_by_str,
                avg_latency_ms=0.0,
                total_tokens=0,
                composite_score=best_accepted_composite,
                project_id=project_id,
                experiment_id=experiment_id,
                trial_id=f"trial_{experiment_id}_{i}",
                config_snapshot=best_accepted_config,
                score_improvement=0.0,
                rejection_reason=rejection_msg,
                proposal_status="invalid_proposal",
                db_path=db_path
            )
            if on_iteration_callback:
                await on_iteration_callback({
                    "iteration_number": i,
                    "hypothesis": hypothesis,
                    "param": param or "None",
                    "old_value": str(old_val),
                    "new_value": str(raw_new_val),
                    "old_score": best_accepted_score,
                    "new_score": best_accepted_score,
                    "accepted": 0,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "motivated_by": motivated_by_str,
                    "avg_latency_ms": 0.0,
                    "total_tokens": 0,
                    "composite_score": best_accepted_composite,
                    "rejection_reason": rejection_msg
                })
            continue

        # 6. Execute isolated evaluation
        print(f"Evaluating candidate: Change '{param}' from {old_val} -> {cleaned_val}")
        print(f"Hypothesis: {hypothesis}")

        try:
            eval_res = eval_harness.evaluate_config(candidate_config, is_experimental=True)
            new_score = eval_res["aggregate_score"]
            new_latency = eval_res.get("avg_latency_ms", 0.0)
            new_tokens = eval_res.get("total_tokens", 0)
            num_questions = len(eval_res.get("results", []))
            new_grounding = eval_res.get("grounding_rate", 1.0)
            new_composite = compute_composite_score(new_score, new_latency, new_tokens, num_questions, new_grounding)
        except Exception as e:
            err_msg = f"Evaluation crashed: {str(e)}"
            print(f"Trial {i} CRASHED: {err_msg}")
            log_iteration(
                iter_num=i,
                hypothesis=hypothesis,
                param=param,
                old_val=old_val,
                new_val=cleaned_val,
                old_score=best_accepted_score,
                new_score=best_accepted_score,
                accepted=False,
                motivated_by=motivated_by_str,
                avg_latency_ms=0.0,
                total_tokens=0,
                composite_score=best_accepted_composite,
                project_id=project_id,
                experiment_id=experiment_id,
                trial_id=f"trial_{experiment_id}_{i}",
                config_snapshot=candidate_config,
                score_improvement=0.0,
                rejection_reason=err_msg,
                proposal_status="evaluation_failed",
                db_path=db_path
            )
            continue

        # 7. Decision rule: Must strictly outperform the best accepted composite score
        accepted = bool(new_composite > best_accepted_composite)
        improvement = round(new_composite - best_accepted_composite, 4)

        if accepted:
            rejection_reason = ""
            print(f">>> Proposal ACCEPTED! (Composite: {best_accepted_composite:.4f} -> {new_composite:.4f} | +{improvement:.4f})")
            
            # Update state
            best_accepted_score = new_score
            best_accepted_composite = new_composite
            best_accepted_config = candidate_config.copy()
            last_eval_results = eval_res["results"]

            # Save to production config and promote index
            save_config(best_accepted_config)
            rag_pipeline.promote_index_to_production(
                chunk_size=best_accepted_config["chunk_size"],
                chunk_overlap=best_accepted_config["chunk_overlap"]
            )
        else:
            if new_composite == best_accepted_composite:
                rejection_reason = f"Candidate composite score ({new_composite:.4f}) equal to baseline; no improvement demonstrated."
            else:
                rejection_reason = f"Candidate composite score ({new_composite:.4f}) is lower than current best ({best_accepted_composite:.4f})."
            print(f">>> Proposal REJECTED: {rejection_reason}")

        # 8. Log trial to SQLite with immutable snapshot
        log_iteration(
            iter_num=i,
            hypothesis=hypothesis,
            param=param,
            old_val=old_val,
            new_val=cleaned_val,
            old_score=best_accepted_score if accepted else best_accepted_score,
            new_score=new_score,
            accepted=accepted,
            motivated_by=motivated_by_str,
            avg_latency_ms=new_latency,
            total_tokens=new_tokens,
            composite_score=new_composite,
            project_id=project_id,
            experiment_id=experiment_id,
            trial_id=f"trial_{experiment_id}_{i}",
            config_snapshot=candidate_config,
            score_improvement=improvement if accepted else 0.0,
            rejection_reason=rejection_reason,
            proposal_status="success",
            db_path=db_path
        )

        # Save granular question evaluations to SQLite
        if eval_res.get("results"):
            db.save_question_evaluations(
                trial_id=f"trial_{experiment_id}_{i}",
                experiment_id=experiment_id,
                iteration_number=i,
                question_results=eval_res["results"],
                db_path=db_path
            )

        # 9. Notify via callback / WebSocket
        if on_iteration_callback:
            await on_iteration_callback({
                "iteration_number": i,
                "hypothesis": hypothesis,
                "param": param,
                "old_value": str(old_val),
                "new_value": str(cleaned_val),
                "old_score": best_accepted_score if accepted else best_accepted_score,
                "new_score": new_score,
                "accepted": 1 if accepted else 0,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "motivated_by": motivated_by_str,
                "avg_latency_ms": new_latency,
                "total_tokens": new_tokens,
                "composite_score": new_composite,
                "project_id": project_id,
                "experiment_id": experiment_id,
                "score_improvement": improvement if accepted else 0.0,
                "rejection_reason": rejection_reason
            })

    print(f"\n--- Optimization Run Finished: {experiment_id} ---")
    print(f"Final Best Score: {best_accepted_score:.4f} | Best Composite: {best_accepted_composite:.4f}\n")
    return {
        "experiment_id": experiment_id,
        "best_score": best_accepted_score,
        "best_composite": best_accepted_composite,
        "best_config": best_accepted_config
    }
