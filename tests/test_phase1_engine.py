# test_phase1_engine.py
# Comprehensive test suite for AutoTune 2.0 Phase 1:
# Core reliability, state management, baseline preservation, snapshot immutability,
# configuration validation, index caching, and backwards compatibility.

import sys
import os
import unittest
import tempfile
import sqlite3
import json
import shutil

ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "engine"))
sys.path.insert(0, ENGINE_DIR)

import db
import config_validator
import agent_loop
import rag_pipeline
import eval_harness

class TestPhase1Engine(unittest.TestCase):

    def setUp(self):
        # Create an isolated temporary directory for testing database and config
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_autotune.db")
        db.apply_migrations(self.test_db_path)
        
        self.valid_base_config = {
            "chunk_size": 500,
            "chunk_overlap": 50,
            "top_k": 3,
            "temperature": 0.0,
            "retrieval_strategy": "vector",
            "prompt_template": "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_accepted_trial_updates_best_score_and_snapshot(self):
        """1. Accepted trial increases best score and records immutable snapshot."""
        exp_id = "exp_test_accepted"
        
        # Log baseline (iteration 0)
        agent_loop.log_iteration(
            iter_num=100,
            hypothesis="Baseline",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.0,
            new_score=0.6,
            accepted=True,
            composite_score=0.65,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            db_path=self.test_db_path
        )

        candidate_config = self.valid_base_config.copy()
        candidate_config["chunk_size"] = 600

        # Trial 101 improves composite score to 0.85 -> should be ACCEPTED
        agent_loop.log_iteration(
            iter_num=101,
            hypothesis="Increase chunk size to 600",
            param="chunk_size",
            old_val=500,
            new_val=600,
            old_score=0.65,
            new_score=0.80,
            accepted=True,
            composite_score=0.85,
            experiment_id=exp_id,
            config_snapshot=candidate_config,
            score_improvement=0.20,
            db_path=self.test_db_path
        )

        best = db.get_experiment_best(experiment_id=exp_id, db_path=self.test_db_path)
        self.assertIsNotNone(best)
        self.assertEqual(best["iteration_number"], 101)
        self.assertEqual(best["composite_score"], 0.85)
        self.assertEqual(best["accepted"], 1)
        
        # Verify snapshot matches candidate
        stored_config = json.loads(best["config_snapshot"])
        self.assertEqual(stored_config["chunk_size"], 600)

    def test_rejected_lower_scoring_trial_preserves_baseline(self):
        """2. Lower scoring trial is rejected and does NOT replace the baseline."""
        exp_id = "exp_test_rejected"

        agent_loop.log_iteration(
            iter_num=200,
            hypothesis="Baseline",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.0,
            new_score=0.75,
            accepted=True,
            composite_score=0.78,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            db_path=self.test_db_path
        )

        # Trial 201 has lower composite score 0.50 -> REJECTED
        candidate_bad = self.valid_base_config.copy()
        candidate_bad["top_k"] = 1
        rejection_reason = "Composite score 0.50 did not exceed baseline 0.78"

        agent_loop.log_iteration(
            iter_num=201,
            hypothesis="Reduce top_k to 1",
            param="top_k",
            old_val=3,
            new_val=1,
            old_score=0.78,
            new_score=0.45,
            accepted=False,
            composite_score=0.50,
            experiment_id=exp_id,
            config_snapshot=candidate_bad,
            score_improvement=0.0,
            rejection_reason=rejection_reason,
            db_path=self.test_db_path
        )

        # Query best accepted trial
        best = db.get_experiment_best(experiment_id=exp_id, db_path=self.test_db_path)
        self.assertEqual(best["iteration_number"], 200, "Rejected trial must NEVER become best trial!")
        self.assertEqual(best["composite_score"], 0.78)

        # Verify trial 201 is logged as rejected with reason
        trials = db.get_experiment_trials(experiment_id=exp_id, db_path=self.test_db_path)
        trial_201 = [t for t in trials if t["iteration_number"] == 201][0]
        self.assertEqual(trial_201["accepted"], 0)
        self.assertEqual(trial_201["rejection_reason"], rejection_reason)

    def test_equal_score_trial_is_rejected(self):
        """3. Equal-score candidate is rejected because it does not improve upon baseline."""
        exp_id = "exp_test_equal"

        agent_loop.log_iteration(
            iter_num=300,
            hypothesis="Baseline",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.0,
            new_score=0.80,
            accepted=True,
            composite_score=0.80,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            db_path=self.test_db_path
        )

        # Candidate with identical score 0.80
        agent_loop.log_iteration(
            iter_num=301,
            hypothesis="Change temperature to 0.1",
            param="temperature",
            old_val=0.0,
            new_val=0.1,
            old_score=0.80,
            new_score=0.80,
            accepted=False,
            composite_score=0.80,
            experiment_id=exp_id,
            score_improvement=0.0,
            rejection_reason="Candidate composite score (0.8000) equal to baseline; no improvement demonstrated.",
            db_path=self.test_db_path
        )

        best = db.get_experiment_best(experiment_id=exp_id, db_path=self.test_db_path)
        self.assertEqual(best["iteration_number"], 300)

    def test_invalid_configuration_rejection(self):
        """4. Invalid proposals fail validation before expensive evaluation runs."""
        # A. chunk_overlap >= chunk_size
        is_valid, err, _, _ = config_validator.validate_proposal(self.valid_base_config, "chunk_overlap", 500)
        self.assertFalse(is_valid)
        self.assertIn("chunk_overlap (500) must be strictly less than chunk_size (500)", err)

        # B. Out of bounds top_k
        is_valid, err, _, _ = config_validator.validate_proposal(self.valid_base_config, "top_k", 0)
        self.assertFalse(is_valid)
        self.assertIn("below minimum", err)

        # C. Invalid retrieval strategy
        is_valid, err, _, _ = config_validator.validate_proposal(self.valid_base_config, "retrieval_strategy", "magic_search")
        self.assertFalse(is_valid)
        self.assertIn("Invalid option", err)

        # D. Missing prompt template placeholders
        is_valid, err, _, _ = config_validator.validate_proposal(self.valid_base_config, "prompt_template", "Answer this: {question}")
        self.assertFalse(is_valid)
        self.assertIn("missing required placeholder '{context}'", err)

        # E. Unknown parameter
        is_valid, err, _, _ = config_validator.validate_proposal(self.valid_base_config, "nonexistent_knob", 42)
        self.assertFalse(is_valid)
        self.assertIn("Unknown parameter", err)

    def test_failed_agent_proposal_explicit_recording(self):
        """5. Failed LLM proposal is explicitly logged without silent top_k fallback."""
        exp_id = "exp_test_failed_proposal"
        
        agent_loop.log_iteration(
            iter_num=400,
            hypothesis="Proposal generation failed.",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.70,
            new_score=0.70,
            accepted=False,
            composite_score=0.70,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            score_improvement=0.0,
            rejection_reason="LLM failed to generate a valid proposal after 3 attempts.",
            proposal_status="failed_proposal",
            db_path=self.test_db_path
        )

        trials = db.get_experiment_trials(experiment_id=exp_id, db_path=self.test_db_path)
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0]["proposal_status"], "failed_proposal")
        self.assertEqual(trials[0]["param"], "None")
        self.assertIn("failed to generate a valid proposal", trials[0]["rejection_reason"])

    def test_missing_evaluation_result_or_crash(self):
        """6. Evaluation crash is logged safely without corrupting database or best score."""
        exp_id = "exp_test_crash"

        agent_loop.log_iteration(
            iter_num=500,
            hypothesis="Baseline",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.0,
            new_score=0.70,
            accepted=True,
            composite_score=0.70,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            db_path=self.test_db_path
        )

        agent_loop.log_iteration(
            iter_num=501,
            hypothesis="Test crash recovery",
            param="chunk_size",
            old_val=500,
            new_val=800,
            old_score=0.70,
            new_score=0.70,
            accepted=False,
            composite_score=0.70,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            score_improvement=0.0,
            rejection_reason="Evaluation crashed: CUDA out of memory / Network timeout",
            proposal_status="evaluation_failed",
            db_path=self.test_db_path
        )

        best = db.get_experiment_best(experiment_id=exp_id, db_path=self.test_db_path)
        self.assertEqual(best["iteration_number"], 500)
        self.assertEqual(best["composite_score"], 0.70)

        trials = db.get_experiment_trials(experiment_id=exp_id, db_path=self.test_db_path)
        crashed = [t for t in trials if t["iteration_number"] == 501][0]
        self.assertEqual(crashed["proposal_status"], "evaluation_failed")

    def test_multiple_independent_experiment_ids(self):
        """7. Multiple experiments run independently without cross-contaminating histories."""
        exp_a = "exp_alpha"
        exp_b = "exp_beta"

        # Experiment Alpha
        agent_loop.log_iteration(
            iter_num=601,
            hypothesis="Alpha Baseline",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.0,
            new_score=0.60,
            accepted=True,
            composite_score=0.60,
            experiment_id=exp_a,
            config_snapshot=self.valid_base_config,
            db_path=self.test_db_path
        )

        # Experiment Beta
        cfg_b = self.valid_base_config.copy()
        cfg_b["top_k"] = 5
        agent_loop.log_iteration(
            iter_num=602,
            hypothesis="Beta Baseline",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.0,
            new_score=0.90,
            accepted=True,
            composite_score=0.92,
            experiment_id=exp_b,
            config_snapshot=cfg_b,
            db_path=self.test_db_path
        )

        best_a = db.get_experiment_best(experiment_id=exp_a, db_path=self.test_db_path)
        best_b = db.get_experiment_best(experiment_id=exp_b, db_path=self.test_db_path)

        self.assertEqual(best_a["experiment_id"], exp_a)
        self.assertEqual(best_a["composite_score"], 0.60)

        self.assertEqual(best_b["experiment_id"], exp_b)
        self.assertEqual(best_b["composite_score"], 0.92)

        trials_a = db.get_experiment_trials(experiment_id=exp_a, db_path=self.test_db_path)
        trials_b = db.get_experiment_trials(experiment_id=exp_b, db_path=self.test_db_path)

        self.assertEqual(len(trials_a), 1)
        self.assertEqual(len(trials_b), 1)

    def test_historical_configuration_reconstruction(self):
        """8. Exact historical configuration is reconstructed from immutable snapshots."""
        cfg_initial = self.valid_base_config.copy()
        snap_id, canonical_json = config_validator.create_config_snapshot(cfg_initial, db_path=self.test_db_path)
        self.assertTrue(snap_id.startswith("snap_"))

        reconstructed = json.loads(canonical_json)
        self.assertEqual(reconstructed["chunk_size"], 500)
        self.assertEqual(reconstructed["chunk_overlap"], 50)
        self.assertEqual(reconstructed["top_k"], 3)

    def test_database_persistence_after_restart(self):
        """9. Persistence across application restart / re-connections."""
        exp_id = "exp_persistence"

        agent_loop.log_iteration(
            iter_num=700,
            hypothesis="Persistence baseline",
            param="None",
            old_val="None",
            new_val="None",
            old_score=0.0,
            new_score=0.75,
            accepted=True,
            composite_score=0.77,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            db_path=self.test_db_path
        )

        # Simulate complete restart: reopen connection to test database
        new_conn = db.get_connection(self.test_db_path)
        cursor = new_conn.cursor()
        cursor.execute("SELECT iteration_number, experiment_id, accepted, composite_score FROM iterations WHERE iteration_number = 700")
        row = cursor.fetchone()
        new_conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["iteration_number"], 700)
        self.assertEqual(row["experiment_id"], exp_id)
        self.assertEqual(row["accepted"], 1)
        self.assertEqual(row["composite_score"], 0.77)

    def test_corpus_fingerprinting_and_index_cache_keys(self):
        """10. Deterministic corpus fingerprinting and cache key calculation."""
        fp1 = rag_pipeline.get_corpus_fingerprint()
        fp2 = rag_pipeline.get_corpus_fingerprint()
        self.assertEqual(fp1, fp2, "Corpus fingerprint must be deterministic across calls")

        key1 = rag_pipeline.get_index_cache_key(500, 50)
        key2 = rag_pipeline.get_index_cache_key(500, 50)
        key3 = rag_pipeline.get_index_cache_key(600, 50)

        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3, "Different chunk parameters must have different cache keys")
        self.assertTrue(key1.startswith("idx_"))

    def test_llm_structured_error_metadata(self):
        """11. LLM failure returns structured metadata with provider and category."""
        # Point to an unreachable port to test error classification
        old_ollama = os.environ.get("OLLAMA_URL")
        os.environ["OLLAMA_URL"] = "http://127.0.0.1:59999"
        old_gemini = os.environ.get("GEMINI_API_KEY")
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

        try:
            text, is_err, err_info = rag_pipeline.call_llm("test", 0.0, return_metadata=True)
            self.assertTrue(is_err)
            self.assertIsNotNone(err_info)
            self.assertEqual(err_info["provider"], "ollama")
            self.assertEqual(err_info["category"], "connection_refused")
            self.assertIn("Cannot connect to Ollama", err_info["message"])
        finally:
            if old_ollama:
                os.environ["OLLAMA_URL"] = old_ollama
            else:
                os.environ.pop("OLLAMA_URL", None)
            if old_gemini:
                os.environ["GEMINI_API_KEY"] = old_gemini

    def test_baseline_and_proposal_status_representation(self):
        """12. Distinct representation of Baseline vs Proposal Unavailable vs Parameter Changes."""
        exp_id = "exp_test_status_repr"

        # Baseline trial
        agent_loop.log_iteration(
            iter_num=800,
            hypothesis="Baseline evaluation of initial configuration.",
            param="[Baseline]",
            old_val="N/A",
            new_val="N/A",
            old_score=0.0,
            new_score=0.70,
            accepted=True,
            composite_score=0.72,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            proposal_status="baseline",
            db_path=self.test_db_path
        )

        # Unavailable proposal trial
        agent_loop.log_iteration(
            iter_num=801,
            hypothesis="Proposal generation failed.",
            param="[Unavailable]",
            old_val="N/A",
            new_val="N/A",
            old_score=0.70,
            new_score=0.70,
            accepted=False,
            composite_score=0.72,
            experiment_id=exp_id,
            config_snapshot=self.valid_base_config,
            rejection_reason="Proposal Unavailable [ollama:connection_refused]",
            proposal_status="failed_proposal",
            db_path=self.test_db_path
        )

        trials = db.get_experiment_trials(experiment_id=exp_id, db_path=self.test_db_path)
        base = [t for t in trials if t["iteration_number"] == 800][0]
        failed = [t for t in trials if t["iteration_number"] == 801][0]

        self.assertEqual(base["param"], "[Baseline]")
        self.assertEqual(base["proposal_status"], "baseline")
        self.assertEqual(failed["param"], "[Unavailable]")
        self.assertEqual(failed["proposal_status"], "failed_proposal")
        self.assertIn("connection_refused", failed["rejection_reason"])

if __name__ == "__main__":
    unittest.main()

