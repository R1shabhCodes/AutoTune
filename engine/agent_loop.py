# agent_loop.py
# Core optimization loop that proposes config changes, evaluates them, and logs results.
# This file is fixed and is NOT modified by the optimization agent.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import sqlite3
import datetime
import importlib
import urllib.request
import urllib.error
import config
import eval_harness

engine_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(engine_dir, "autotune.db")

# Multi-objective optimization weights
W_ACCURACY = 0.7
W_LATENCY = 0.2
W_TOKENS = 0.1
LATENCY_BUDGET_MS = 5000.0  # 5 seconds budget per question
TOKEN_BUDGET = 2000         # token budget per question

def compute_composite_score(accuracy: float, avg_latency_ms: float, total_tokens: int, num_questions: int, grounding_rate: float = 1.0) -> float:
    """Computes a weighted composite score from accuracy, latency, and token usage, penalized by grounding failures."""
    latency_score = max(0.0, 1.0 - avg_latency_ms / LATENCY_BUDGET_MS)
    avg_tokens = total_tokens / max(num_questions, 1)
    token_score = max(0.0, 1.0 - avg_tokens / TOKEN_BUDGET)
    
    # Calculate base composite score
    base_score = W_ACCURACY * accuracy + W_LATENCY * latency_score + W_TOKENS * token_score
    
    # Apply a penalty for ungrounded numbers (hallucinations)
    grounding_penalty = 0.3 * (1.0 - grounding_rate)
    
    return round(max(0.0, base_score - grounding_penalty), 4)

def init_db():
    """Initializes the SQLite database with the iterations table and column updates."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS iterations (
            iteration_number INTEGER PRIMARY KEY,
            hypothesis TEXT,
            param TEXT,
            old_value TEXT,
            new_value TEXT,
            old_score REAL,
            new_score REAL,
            accepted INTEGER,
            timestamp TEXT,
            motivated_by TEXT
        )
    """)
    # Schema migrations for backward-compatibility
    migrations = [
        "ALTER TABLE iterations ADD COLUMN motivated_by TEXT",
        "ALTER TABLE iterations ADD COLUMN avg_latency_ms REAL",
        "ALTER TABLE iterations ADD COLUMN total_tokens INTEGER",
        "ALTER TABLE iterations ADD COLUMN composite_score REAL",
    ]
    for sql in migrations:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def log_iteration(iter_num: int, hypothesis: str, param: str, old_val: str, new_val: str, old_score: float, new_score: float, accepted: bool, motivated_by: str = "", avg_latency_ms: float = 0.0, total_tokens: int = 0, composite_score: float = 0.0):
    """Inserts a new optimization iteration record into the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO iterations (iteration_number, hypothesis, param, old_value, new_value, old_score, new_score, accepted, timestamp, motivated_by, avg_latency_ms, total_tokens, composite_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        iter_num,
        hypothesis,
        param,
        str(old_val),
        str(new_val),
        old_score,
        new_score,
        1 if accepted else 0,
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        motivated_by,
        avg_latency_ms,
        total_tokens,
        composite_score
    ))
    conn.commit()
    conn.close()

def get_history(limit: int = 10) -> list:
    """Retrieves the last N evaluation iterations from the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT iteration_number, hypothesis, param, old_value, new_value, old_score, new_score, accepted
        FROM iterations
        ORDER BY iteration_number DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]
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
        
    # Also save to apps/rag_finance/config.json to sync the production application
    target_config_path = os.path.abspath(os.path.join(engine_dir, "..", "apps", "rag_finance", "config.json"))
    if os.path.exists(os.path.dirname(target_config_path)):
        try:
            with open(target_config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=2)
            print(f"Synced best config to target app at {target_config_path}")
        except Exception as e:
            print(f"Failed to sync config to target app: {e}")


def call_llm_json(prompt: str, system_prompt: str) -> dict:
    """
    Calls the LLM (Gemini or Ollama) requesting JSON output,
    and returns the parsed Python dictionary.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    env_path = os.path.join(engine_dir, ".env")
    if not gemini_key and os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    if k.strip() == "GEMINI_API_KEY":
                        gemini_key = v.strip().strip('"').strip("'")
                        break

    if gemini_key:
        model = "gemini-2.5-flash"
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
                return json.loads(text)
        except Exception as e:
            print(f"Gemini proposal generation error: {e}")
            raise e
    else:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "qwen2.5:1.5b",
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
                return json.loads(text)
        except Exception as e:
            print(f"Ollama proposal generation error: {e}")
            raise e

def generate_proposal(current_config: dict, history: list, last_eval_results: list = None) -> dict:
    """Uses LLM to generate a param tuning proposal, with retry/fallback mechanism."""
    # Read persona instructions
    program_path = os.path.join(engine_dir, "program.md")
    with open(program_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # Format the current state and history
    prompt = f"Here is the CURRENT config of the RAG system:\n"
    prompt += json.dumps(current_config, indent=2) + "\n\n"
    
    # Extract failing questions if present
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

    # Retry loop for LLM json generation
    for attempt in range(3):
        try:
            proposal = call_llm_json(prompt, system_prompt)
            # Validate essential fields
            if "param" in proposal and "new_value" in proposal:
                return proposal
        except Exception as e:
            print(f"JSON proposal attempt {attempt+1} failed: {e}")
            
    # Absolute fallback to prevent crashing the agent loop
    print("Warning: LLM failed to generate a valid proposal after 3 attempts. Using fallback.")
    # Alternate simple parameter change
    fallback_param = "top_k"
    current_val = current_config.get(fallback_param, 2)
    new_val = current_val + 1 if current_val < 5 else 2
    return {
        "hypothesis": "Fallback modification due to LLM generator failure.",
        "param": fallback_param,
        "old_value": current_val,
        "new_value": new_val
    }

def clean_value(param: str, value):
    """Coerces type and sanitizes proposed values based on expected types."""
    try:
        if param in ["chunk_size", "chunk_overlap", "top_k"]:
            return int(float(value)) # handles strings and floats safely
        elif param in ["temperature"]:
            return float(value)
        elif param in ["prompt_template"]:
            # Make sure prompt has correct placeholders
            val_str = str(value)
            if "{context}" not in val_str or "{question}" not in val_str:
                raise ValueError("Prompt template missing placeholders")
            return val_str
        elif param in ["retrieval_strategy"]:
            val_str = str(value).lower().strip()
            if val_str not in ["vector", "keyword", "hybrid"]:
                raise ValueError(f"Invalid retrieval strategy: {val_str}. Must be one of: vector, keyword, hybrid")
            return val_str
    except Exception as e:
        print(f"Error cleaning param {param} value {value}: {e}")
        return None
    return value

async def run_optimization(num_iterations: int, on_iteration_callback=None):
    """
    Main loop that coordinates the optimization process.
    Runs for num_iterations, executing eval, checking scores, updating config,
    logging to SQLite, and streaming notifications via callback.
    """
    init_db()
    
    # Track the last evaluation results to inject failures into proposal prompt
    last_eval_results = []
    
    # 1. Evaluate baseline first (Iteration 0)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM iterations WHERE iteration_number = 0")
    has_baseline = cursor.fetchone()[0] > 0
    conn.close()
    
    importlib.reload(config)
    current_config = config.CONFIG.copy()
    
    if has_baseline:
        print("Running evaluation on current best config to identify failing questions...")
        current_res = eval_harness.evaluate_config(current_config)
        last_eval_results = current_res["results"]
    else:
        print("--- Running Baseline Evaluation (Iteration 0) ---")
        baseline_res = eval_harness.evaluate_config(current_config)
        baseline_score = baseline_res["aggregate_score"]
        last_eval_results = baseline_res["results"]
        
        log_iteration(
            iter_num=0,
            hypothesis="Baseline evaluation of initial configuration.",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.0,
            new_score=baseline_score,
            accepted=True,
            motivated_by=""
        )
        
        if on_iteration_callback:
            await on_iteration_callback({
                "iteration_number": 0,
                "hypothesis": "Baseline evaluation of initial configuration.",
                "param": "None",
                "old_value": "None",
                "new_value": "None",
                "old_score": 0.0,
                "new_score": baseline_score,
                "accepted": 1,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "motivated_by": ""
            })
    
    # Get current best score and compute initial composite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT new_score FROM iterations ORDER BY iteration_number DESC LIMIT 1")
    current_best_score = cursor.fetchone()[0]
    
    # Compute initial composite score from the baseline/current evaluation
    baseline_latency = current_res.get("avg_latency_ms", 0.0) if has_baseline and 'current_res' in dir() else 0.0
    baseline_tokens = current_res.get("total_tokens", 0) if has_baseline and 'current_res' in dir() else 0
    baseline_num_q = len(current_res.get("results", [])) if has_baseline and 'current_res' in dir() else 1
    baseline_grounding = current_res.get("grounding_rate", 1.0) if has_baseline and 'current_res' in dir() else 1.0
    current_best_composite = compute_composite_score(current_best_score, baseline_latency, baseline_tokens, baseline_num_q, baseline_grounding)
    
    # Find next iteration index
    cursor.execute("SELECT MAX(iteration_number) FROM iterations")
    start_iter = (cursor.fetchone()[0] or 0) + 1
    conn.close()
    
    for i in range(start_iter, start_iter + num_iterations):
        print(f"\n--- Starting Optimization Iteration {i} (Current Best Score: {current_best_score:.4f}) ---")
        
        # 1. Fetch history from DB
        history = get_history(limit=10)
        
        # 2. Get LLM Proposal (passing the previous failure results)
        gemini_key = os.environ.get("GEMINI_API_KEY")
        env_path = os.path.join(engine_dir, ".env")
        if not gemini_key and os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        if k.strip() == "GEMINI_API_KEY" and v.strip():
                            gemini_key = v.strip().strip('"').strip("'")
                            break
        if gemini_key:
            import time
            time.sleep(4.0)
        
        # Extract targeted questions for logging
        motivated_by_str = ""
        if last_eval_results:
            failing_qs = [r for r in last_eval_results if not r.get("passed", False)]
            if failing_qs:
                motivated_by_str = " | ".join([f["question"] for f in failing_qs[:3]])

        proposal = generate_proposal(current_config, history, last_eval_results)
        param = proposal.get("param")
        hypothesis = proposal.get("hypothesis", "No hypothesis provided.")
        raw_new_val = proposal.get("new_value")
        
        # 3. Validate & Clean
        new_val = clean_value(param, raw_new_val)
        if new_val is None:
            print(f"Skipping iteration {i}: Invalid value proposed for '{param}': {raw_new_val}")
            log_iteration(i, f"Rejected due to invalid parameter value: {raw_new_val}", param or "None", current_config.get(param, "N/A"), str(raw_new_val), current_best_score, current_best_score, False, motivated_by_str)
            if on_iteration_callback:
                await on_iteration_callback({
                    "iteration_number": i,
                    "hypothesis": f"Rejected due to invalid parameter value: {raw_new_val}",
                    "param": param or "None",
                    "old_value": str(current_config.get(param, "N/A")),
                    "new_value": str(raw_new_val),
                    "old_score": current_best_score,
                    "new_score": current_best_score,
                    "accepted": 0,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "motivated_by": motivated_by_str
                })
            continue
            
        old_val = current_config.get(param)
        
        # Additional safety check for chunk overlap
        proposed_chunk_size = new_val if param == "chunk_size" else current_config.get("chunk_size", 200)
        proposed_overlap = new_val if param == "chunk_overlap" else current_config.get("chunk_overlap", 20)
        
        if proposed_overlap >= proposed_chunk_size:
            print(f"Skipping iteration {i}: Proposed overlap {proposed_overlap} >= size {proposed_chunk_size}")
            log_iteration(i, f"Rejected due to chunk_overlap ({proposed_overlap}) >= chunk_size ({proposed_chunk_size})", param, old_val, new_val, current_best_score, current_best_score, False, motivated_by_str)
            if on_iteration_callback:
                await on_iteration_callback({
                    "iteration_number": i,
                    "hypothesis": f"Rejected due to chunk_overlap ({proposed_overlap}) >= chunk_size ({proposed_chunk_size})",
                    "param": param,
                    "old_value": str(old_val),
                    "new_value": str(new_val),
                    "old_score": current_best_score,
                    "new_score": current_best_score,
                    "accepted": 0,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "motivated_by": motivated_by_str
                })
            continue

        # 4. Run evaluation with proposed config COPY
        proposed_config = current_config.copy()
        proposed_config[param] = new_val
        
        print(f"Evaluating proposal: Change '{param}' from {old_val} -> {new_val}")
        print(f"Hypothesis: {hypothesis}")
        
        try:
            eval_res = eval_harness.evaluate_config(proposed_config)
            new_score = eval_res["aggregate_score"]
            new_latency = eval_res.get("avg_latency_ms", 0.0)
            new_tokens = eval_res.get("total_tokens", 0)
            num_questions = len(eval_res.get("results", []))
            new_grounding = eval_res.get("grounding_rate", 1.0)
            new_composite = compute_composite_score(new_score, new_latency, new_tokens, num_questions, new_grounding)
        except Exception as e:
            print(f"Evaluation crashed for proposed config: {e}")
            log_iteration(i, f"Evaluation crashed: {str(e)}", param, old_val, new_val, current_best_score, current_best_score, False, motivated_by_str)
            continue
            
        # 5. Decide (Accept if composite score improves)
        accepted = new_composite > current_best_composite
        
        if accepted:
            print(f">>> Proposal ACCEPTED (Composite: {current_best_composite:.4f} -> {new_composite:.4f} | Accuracy: {new_score:.4f} | Latency: {new_latency:.0f}ms)")
            current_best_score = new_score
            current_best_composite = new_composite
            current_config = proposed_config
            # Save the new current configuration to config.py
            save_config(current_config)
            # Update failure results for the next iteration
            last_eval_results = eval_res["results"]
        else:
            print(f">>> Proposal REJECTED (Composite {new_composite:.4f} did not outperform current best {current_best_composite:.4f})")
            
        # 6. Log iteration
        log_iteration(
            iter_num=i,
            hypothesis=hypothesis,
            param=param,
            old_val=old_val,
            new_val=new_val,
            old_score=current_best_score if accepted else current_best_score,
            new_score=new_score,
            accepted=accepted,
            motivated_by=motivated_by_str,
            avg_latency_ms=new_latency,
            total_tokens=new_tokens,
            composite_score=new_composite
        )
        
        # 7. Notify via callback
        if on_iteration_callback:
            await on_iteration_callback({
                "iteration_number": i,
                "hypothesis": hypothesis,
                "param": param,
                "old_value": str(old_val),
                "new_value": str(new_val),
                "old_score": current_best_score if accepted else current_best_score,
                "new_score": new_score,
                "accepted": 1 if accepted else 0,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "motivated_by": motivated_by_str,
                "avg_latency_ms": new_latency,
                "total_tokens": new_tokens,
                "composite_score": new_composite
            })
            
    print("\n--- Optimization Run Finished ---")
