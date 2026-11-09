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

