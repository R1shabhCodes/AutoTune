# db.py
# Database access layer and versioned migrations for AutoTune.
# Preserves all existing SQLite data while adding structured experiment & snapshot tracking.

import os
import json
import sqlite3
import datetime
import logging

logger = logging.getLogger("autotune.db")

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ENGINE_DIR, "autotune.db")

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Returns a SQLite connection with Row factory and busy timeout."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def apply_migrations(db_path: str = DB_PATH):
    """
    Applies versioned, non-destructive schema migrations.
    Safely preserves all existing rows and historical iteration logs.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Create migrations tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)

        # Check applied migrations
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}

        # -------------------------------------------------------------
        # Migration 1: Base iterations table + legacy backward compatibility
        # -------------------------------------------------------------
        if 1 not in applied:
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
                    motivated_by TEXT,
                    avg_latency_ms REAL,
                    total_tokens INTEGER,
                    composite_score REAL
                )
            """)

            # Add columns to iterations safely if not already present
            new_columns = [
                ("motivated_by", "TEXT"),
                ("avg_latency_ms", "REAL"),
                ("total_tokens", "INTEGER"),
                ("composite_score", "REAL"),
                ("project_id", "TEXT DEFAULT 'default'"),
                ("experiment_id", "TEXT DEFAULT 'exp_legacy'"),
                ("trial_id", "TEXT"),
                ("dataset_id", "TEXT DEFAULT 'eval_set_tuning'"),
                ("config_snapshot_id", "TEXT"),
                ("config_snapshot", "TEXT"),
                ("score_improvement", "REAL DEFAULT 0.0"),
                ("rejection_reason", "TEXT"),
                ("proposal_status", "TEXT DEFAULT 'success'")
            ]

            cursor.execute("PRAGMA table_info(iterations)")
            existing_cols = {row[1] for row in cursor.fetchall()}

            for col_name, col_type in new_columns:
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE iterations ADD COLUMN {col_name} {col_type}")

            # Create experiments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    project_id TEXT DEFAULT 'default',
                    name TEXT,
                    status TEXT DEFAULT 'active',
                    baseline_config TEXT,
                    best_config TEXT,
                    baseline_score REAL,
                    best_score REAL,
                    baseline_composite REAL,
                    best_composite REAL,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            # Create config snapshots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    config_hash TEXT UNIQUE,
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Backfill legacy iterations
            cursor.execute("""
                UPDATE iterations 
                SET project_id = 'default' 
                WHERE project_id IS NULL
            """)
            cursor.execute("""
                UPDATE iterations 
                SET experiment_id = 'exp_legacy' 
                WHERE experiment_id IS NULL
            """)
            cursor.execute("""
                UPDATE iterations 
                SET trial_id = 'trial_legacy_' || iteration_number 
                WHERE trial_id IS NULL
            """)
            cursor.execute("""
                UPDATE iterations 
                SET dataset_id = 'eval_set_tuning' 
                WHERE dataset_id IS NULL
            """)
            cursor.execute("""
                UPDATE iterations 
                SET proposal_status = 'success' 
                WHERE proposal_status IS NULL
            """)

            # Ensure an experiment record exists for legacy iterations if there are rows
            cursor.execute("SELECT COUNT(*) FROM iterations WHERE experiment_id = 'exp_legacy'")
            legacy_count = cursor.fetchone()[0]
            if legacy_count > 0:
                cursor.execute("SELECT COUNT(*) FROM experiments WHERE experiment_id = 'exp_legacy'")
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        SELECT new_score, composite_score FROM iterations 
                        WHERE experiment_id = 'exp_legacy' AND accepted = 1 
                        ORDER BY iteration_number DESC LIMIT 1
                    """)
                    best_row = cursor.fetchone()
                    best_sc = best_row[0] if best_row else 0.0
                    best_cp = best_row[1] if best_row and best_row[1] is not None else best_sc

                    cursor.execute("""
                        INSERT INTO experiments (
                            experiment_id, project_id, name, status, baseline_score, best_score, baseline_composite, best_composite, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        'exp_legacy', 'default', 'Legacy Experiments (v1.0)', 'completed',
                        0.0, best_sc, 0.0, best_cp,
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

            cursor.execute("""
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (1, 'initial_v2_schema_and_legacy_backfill', ?)
            """, (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))

            conn.commit()
            logger.info("Applied migration 1: initial_v2_schema_and_legacy_backfill")

        # -------------------------------------------------------------
        # Migration 2: Phase 2 Question-Level Evaluations Table
        # -------------------------------------------------------------
        if 2 not in applied:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS question_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trial_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    iteration_number INTEGER,
                    sample_id TEXT,
                    question TEXT NOT NULL,
                    expected_answer TEXT,
                    generated_answer TEXT,
                    retrieved_contexts TEXT,
                    expected_term_pass_rate REAL,
                    exact_match REAL,
                    numerical_grounding_passed INTEGER,
                    ungrounded_numbers TEXT,
                    citation_present INTEGER,
                    faithfulness REAL,
                    answer_relevancy REAL,
                    context_precision REAL,
                    context_recall REAL,
                    latency_ms REAL,
                    retrieval_ms REAL,
                    generation_ms REAL,
                    tokens INTEGER,
                    cost REAL,
                    is_error INTEGER,
                    failure_category TEXT,
                    error_info TEXT,
                    evaluation_metadata TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_question_evaluations_trial 
                ON question_evaluations(trial_id)
            """)

            cursor.execute("""
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (2, 'phase2_question_evaluations_table', ?)
            """, (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))

            conn.commit()
            logger.info("Applied migration 2: phase2_question_evaluations_table")

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to apply database migrations: {e}")
        raise e
    finally:
        conn.close()

def log_trial_record(
    iter_num: int,
    hypothesis: str,
    param: str,
    old_val,
    new_val,
    old_score: float,
    new_score: float,
    accepted: bool,
    motivated_by: str = "",
    avg_latency_ms: float = 0.0,
    total_tokens: int = 0,
    composite_score: float = 0.0,
    project_id: str = "default",
    experiment_id: str = "exp_legacy",
    trial_id: str = None,
    dataset_id: str = "eval_set_tuning",
    config_snapshot_id: str = None,
    config_snapshot: dict = None,
    score_improvement: float = 0.0,
    rejection_reason: str = "",
    proposal_status: str = "success",
    db_path: str = DB_PATH
):
    """
    Atomically writes a trial record to the database with all tracking fields.
    """
    if trial_id is None:
        trial_id = f"trial_{experiment_id}_{iter_num}"

    config_json_str = json.dumps(config_snapshot, sort_keys=True) if config_snapshot else None

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        with conn:
            cursor.execute("""
                INSERT INTO iterations (
                    iteration_number, hypothesis, param, old_value, new_value,
                    old_score, new_score, accepted, timestamp, motivated_by,
                    avg_latency_ms, total_tokens, composite_score,
                    project_id, experiment_id, trial_id, dataset_id,
                    config_snapshot_id, config_snapshot, score_improvement,
                    rejection_reason, proposal_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                iter_num,
                hypothesis,
                param,
                str(old_val),
                str(new_val),
                float(old_score),
                float(new_score),
                1 if accepted else 0,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                motivated_by,
                float(avg_latency_ms),
                int(total_tokens),
                float(composite_score),
                project_id,
                experiment_id,
                trial_id,
                dataset_id,
                config_snapshot_id,
                config_json_str,
                float(score_improvement),
                rejection_reason,
                proposal_status
            ))
    finally:
        conn.close()

# Backward-compatibility alias
log_iteration = log_trial_record

def get_experiment_best(experiment_id: str = None, db_path: str = DB_PATH) -> dict:
    """
    Retrieves the best ACCEPTED trial for an experiment.
    Guarantees rejected trials are never returned as the best candidate.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        if experiment_id:
            cursor.execute("""
                SELECT iteration_number, hypothesis, param, old_value, new_value,
                       old_score, new_score, accepted, timestamp, motivated_by,
                       avg_latency_ms, total_tokens, composite_score,
                       project_id, experiment_id, trial_id, config_snapshot,
                       score_improvement, rejection_reason
                FROM iterations
                WHERE experiment_id = ? AND accepted = 1
                ORDER BY iteration_number DESC
                LIMIT 1
            """, (experiment_id,))
        else:
            cursor.execute("""
                SELECT iteration_number, hypothesis, param, old_value, new_value,
                       old_score, new_score, accepted, timestamp, motivated_by,
                       avg_latency_ms, total_tokens, composite_score,
                       project_id, experiment_id, trial_id, config_snapshot,
                       score_improvement, rejection_reason
                FROM iterations
                WHERE accepted = 1
                ORDER BY iteration_number DESC
                LIMIT 1
            """)
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_experiment_trials(experiment_id: str = None, limit: int = None, db_path: str = DB_PATH) -> list:
    """
    Returns trials for an experiment (or all trials if experiment_id is None).
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        query = """
            SELECT iteration_number, hypothesis, param, old_value, new_value,
                   old_score, new_score, accepted, timestamp, motivated_by,
                   avg_latency_ms, total_tokens, composite_score,
                   project_id, experiment_id, trial_id, config_snapshot,
                   score_improvement, rejection_reason, proposal_status
            FROM iterations
        """
        params = []
        if experiment_id:
            query += " WHERE experiment_id = ?"
            params.append(experiment_id)

        query += " ORDER BY iteration_number DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_question_evaluations(
    trial_id: str,
    experiment_id: str,
    iteration_number: int,
    question_results: list,
    db_path: str = DB_PATH
):
    """
    Persists question-level granular evaluation telemetry to the database.
    """
    if not question_results:
        return

    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with conn:
            for qr in question_results:
                is_dict = isinstance(qr, dict)
                sample_id = qr.get("sample_id", "") if is_dict else getattr(qr, "sample_id", "")
                question = qr.get("question", "") if is_dict else getattr(qr, "question", "")
                exp_ans = qr.get("expected_answer", "") if is_dict else getattr(qr, "expected_answer", "")
                gen_ans = qr.get("generated_answer", "") if is_dict else getattr(qr, "generated_answer", "")
                contexts = qr.get("retrieved_contexts", []) if is_dict else getattr(qr, "retrieved_contexts", [])
                contexts_json = json.dumps(contexts) if contexts else "[]"
                
                term_rate = qr.get("expected_term_pass_rate", qr.get("score", None)) if is_dict else getattr(qr, "expected_term_pass_rate", None)
                exact = qr.get("exact_match", None) if is_dict else getattr(qr, "exact_match", None)
                num_ground = qr.get("grounding_passed", qr.get("numerical_grounding_passed", None)) if is_dict else getattr(qr, "numerical_grounding_passed", None)
                ungrounded = qr.get("ungrounded_numbers", []) if is_dict else getattr(qr, "ungrounded_numbers", [])
                ungrounded_json = json.dumps(ungrounded) if ungrounded else "[]"
                
                citation_val = qr.get("citation_present", False) if is_dict else getattr(qr, "citation_present", False)
                citation = 1 if citation_val else 0
                
                faithfulness = qr.get("faithfulness", None) if is_dict else getattr(qr, "faithfulness", None)
                relevancy = qr.get("answer_relevancy", None) if is_dict else getattr(qr, "answer_relevancy", None)
                cp = qr.get("context_precision", None) if is_dict else getattr(qr, "context_precision", None)
                cr = qr.get("context_recall", None) if is_dict else getattr(qr, "context_recall", None)
                
                lat = float(qr.get("latency_ms", 0.0) if is_dict else getattr(qr, "latency_ms", 0.0) or 0.0)
                ret_ms = float(qr.get("retrieval_ms", 0.0) if is_dict else getattr(qr, "retrieval_ms", 0.0) or 0.0)
                gen_ms = float(qr.get("generation_ms", 0.0) if is_dict else getattr(qr, "generation_ms", 0.0) or 0.0)
                tok = int(qr.get("tokens", 0) if is_dict else getattr(qr, "tokens", 0) or 0)
                cost = float(qr.get("cost", 0.0) if is_dict else getattr(qr, "cost", 0.0) or 0.0)
                
                is_err_val = qr.get("is_error", False) if is_dict else getattr(qr, "is_error", False)
                is_err = 1 if is_err_val else 0
                
                failure_cat = qr.get("failure_category", None) if is_dict else getattr(qr, "failure_category", None)
                err_info = qr.get("error_info", None) if is_dict else getattr(qr, "error_info", None)
                err_info_json = json.dumps(err_info) if err_info else None
                meta = qr.get("evaluation_metadata", None) if is_dict else getattr(qr, "evaluation_metadata", None)
                meta_json = json.dumps(meta) if meta else None

                cursor.execute("""
                    INSERT INTO question_evaluations (
                        trial_id, experiment_id, iteration_number, sample_id, question,
                        expected_answer, generated_answer, retrieved_contexts,
                        expected_term_pass_rate, exact_match, numerical_grounding_passed,
                        ungrounded_numbers, citation_present, faithfulness, answer_relevancy,
                        context_precision, context_recall, latency_ms, retrieval_ms,
                        generation_ms, tokens, cost, is_error, failure_category,
                        error_info, evaluation_metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trial_id, experiment_id, iteration_number, sample_id, question,
                    exp_ans, gen_ans, contexts_json,
                    term_rate, exact, 1 if num_ground else 0,
                    ungrounded_json, citation, faithfulness, relevancy,
                    cp, cr, lat, ret_ms,
                    gen_ms, tok, cost, is_err, failure_cat,
                    err_info_json, meta_json, now_str
                ))
    finally:
        conn.close()


def get_question_evaluations_for_trial(trial_id: str, db_path: str = DB_PATH) -> list:
    """
    Retrieves all question-level evaluation records for a specific trial.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM question_evaluations 
            WHERE trial_id = ? 
            ORDER BY id ASC
        """, (trial_id,))
        return [dict(r) for r in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


