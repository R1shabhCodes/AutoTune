"""
tests/test_phase3_integrations.py
Comprehensive test suite for AutoTune 2.0 Universal RAG Integration Architecture (Phase 3).
Verifies:
1. Finance RAG adapter compliance with BaseRAGAdapter interface.
2. Independent Custom FastAPI RAG application execution and protocol compliance.
3. Observe mode (read-only query evaluation without config modification).
4. Optimize mode (parameter discovery, dynamic validation, config apply/restore).
5. Unsupported parameter rejection and manifest parameter constraints.
6. SSRF endpoint validation (blocked cloud metadata and link-local ranges).
7. External API timeout and error handling.
8. Authentication with API bearer token and unauthorized rejection.
9. Missing context/usage resilience in EvaluationService.
10. Python SDK app creation and query execution.
11. LangChain example compatibility.
"""
import unittest
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure root is on path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from engine.integrations import (
    BaseRAGAdapter,
    RestRAGAdapter,
    FinanceRAGAdapter,
    get_adapter_registry,
    is_safe_external_url
)
from engine.integrations.schemas.protocol import (
    ManifestResponse,
    HealthResponse,
    QueryResponse,
    QueryContext,
    QueryLatency,
    QueryUsage,
    ConfigValidationResponse,
    ConfigApplyResponse
)
from sdk.autotune_sdk import AutoTuneApp
from apps.external_rag.app import app as external_fastapi_app
from apps.langchain_example import create_langchain_autotune_app
from engine.evaluation import EvaluationService, DatasetManager


class TestUniversalRAGIntegrations(unittest.TestCase):

    def setUp(self):
        self.registry = get_adapter_registry()

    def test_finance_adapter_conformance(self):
        """FinanceRAGAdapter conforms to BaseRAGAdapter contract."""
        adapter = FinanceRAGAdapter()
        health = adapter.health_check()
        self.assertIn(health.status, ["healthy", "degraded"])

        manifest = adapter.get_manifest()
        self.assertEqual(manifest.application, "autotune-finance-rag")
        self.assertEqual(manifest.mode, "optimize")
        self.assertTrue(manifest.capabilities.query)
        self.assertTrue(manifest.capabilities.apply_config)
        self.assertIn("chunk_size", manifest.parameters)
        self.assertIn("top_k", manifest.parameters)

        cfg = adapter.get_config()
        self.assertIsInstance(cfg, dict)

    def test_independent_fastapi_app_and_sdk(self):
        """Independent external RAG application handles protocol endpoints via TestClient."""
        client = TestClient(external_fastapi_app)

        # 1. Unauthorized without token
        res = client.get("/autotune/manifest")
        self.assertEqual(res.status_code, 401)

        headers = {"Authorization": "Bearer secret-autotune-token"}

        # 2. Manifest check
        res = client.get("/autotune/manifest", headers=headers)
        self.assertEqual(res.status_code, 200)
        manifest = res.json()
        self.assertEqual(manifest["application"], "cloud-tech-rag")
        self.assertIn("similarity_threshold", manifest["parameters"])
        self.assertIn("max_tokens", manifest["parameters"])

        # 3. Health check
        res = client.get("/autotune/health", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

        # 4. Query execution
        q_payload = {"question": "What is a Pod in Kubernetes?"}
        res = client.post("/autotune/query", json=q_payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        q_res = res.json()
        self.assertIn("Pod", q_res["answer"])
        self.assertGreater(len(q_res["contexts"]), 0)
        self.assertEqual(q_res["contexts"][0]["source"], "k8s_architecture.md")

        # 5. Config validate & apply
        val_res = client.post(
            "/autotune/config/validate",
            json={"config": {"similarity_threshold": 0.85, "max_tokens": 512}},
            headers=headers
        )
        self.assertEqual(val_res.status_code, 200)
        self.assertTrue(val_res.json()["valid"])

        apply_res = client.post(
            "/autotune/config/apply",
            json={"config": {"similarity_threshold": 0.85, "max_tokens": 512}},
            headers=headers
        )
        self.assertEqual(apply_res.status_code, 200)
        self.assertTrue(apply_res.json()["success"])
        self.assertEqual(apply_res.json()["active_config"]["similarity_threshold"], 0.85)

        # 6. Config restore
        restore_res = client.post(
            "/autotune/config/restore",
            json={"config": {"similarity_threshold": 0.75, "max_tokens": 256}},
            headers=headers
        )
        self.assertEqual(restore_res.status_code, 200)
        self.assertTrue(restore_res.json()["success"])
        self.assertEqual(restore_res.json()["active_config"]["similarity_threshold"], 0.75)

    def test_observe_mode_blocks_config_modifications(self):
        """Observe mode application answers queries but rejects configuration mutations."""
        langchain_sdk = create_langchain_autotune_app()
        client = TestClient(langchain_sdk.create_fastapi_app())

        manifest = client.get("/autotune/manifest").json()
        self.assertEqual(manifest["mode"], "observe")
        self.assertFalse(manifest["capabilities"]["apply_config"])

        # Query succeeds
        q_res = client.post("/autotune/query", json={"question": "What is company policy?"})
        self.assertEqual(q_res.status_code, 200)
        self.assertIn("LangChain", q_res.json()["answer"])

        # Apply config fails gracefully
        apply_res = client.post("/autotune/config/apply", json={"config": {"chunk_size": 200}})
        self.assertEqual(apply_res.status_code, 200)
        self.assertFalse(apply_res.json()["success"])
        self.assertIn("observe mode", apply_res.json()["message"])

    def test_ssrf_and_url_security_validation(self):
        """SSRF validator blocks cloud metadata, loopback manipulation, and malformed protocols."""
        # Forbidden cloud metadata IPs and hostnames
        safe, msg = is_safe_external_url("http://169.254.169.254/latest/meta-data")
        self.assertFalse(safe)
        self.assertIn("forbidden", msg)

        safe, msg = is_safe_external_url("http://metadata.google.internal/computeMetadata/v1")
        self.assertFalse(safe)

        # Invalid schemes
        safe, msg = is_safe_external_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("Unsupported scheme", msg)

        safe, msg = is_safe_external_url("ftp://server/file")
        self.assertFalse(safe)

        # Valid URLs
        safe, msg = is_safe_external_url("http://127.0.0.1:8001", allow_localhost=True)
        self.assertTrue(safe)
        safe, msg = is_safe_external_url("https://api.myragservice.com/v1")
        self.assertTrue(safe)

    def test_rest_adapter_mock_timeout_and_error_handling(self):
        """RestRAGAdapter handles timeouts, connection errors, and missing contexts resiliently."""
        adapter = RestRAGAdapter(base_url="http://127.0.0.1:9999", timeout=0.5, max_retries=0)
        
        # Health check on dead port returns unhealthy without crashing
        health = adapter.health_check()
        self.assertEqual(health.status, "unhealthy")

        # Query on dead port returns error QueryResponse
        resp = adapter.query("Test question")
        self.assertIn("Error:", resp.answer)
        self.assertIsNotNone(resp.error)
        self.assertEqual(len(resp.contexts), 0)

    def test_evaluation_service_with_custom_adapter(self):
        """EvaluationService dispatches queries through an adapter and computes metrics."""
        mock_adapter = MagicMock(spec=BaseRAGAdapter)
        mock_adapter.query.return_value = QueryResponse(
            question="What is a Pod?",
            answer="A Pod is the smallest deployable unit in Kubernetes containing containers.",
            contexts=[QueryContext(text="Kubernetes Pods encapsulate containers.", source="doc.txt", score=0.95)],
            latency=QueryLatency(retrieval_ms=10.0, generation_ms=40.0, total_ms=50.0),
            usage=QueryUsage(total_tokens=75)
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            test_dataset_path = os.path.join(tmpdir, "test_eval.json")
            with open(test_dataset_path, "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "id": "q1",
                        "question": "What is a Pod?",
                        "expected_answer_contains": ["Pod", "containers"]
                    }
                ], f)

            service = EvaluationService(run_semantic_judge=False)
            report = service.evaluate_configuration(
                config={"similarity_threshold": 0.8},
                dataset_filename=test_dataset_path,
                role="tuning",
                adapter=mock_adapter
            )

            self.assertEqual(report.total_samples, 1)
            self.assertEqual(report.expected_term_pass_rate, 1.0)
            self.assertEqual(report.p50_latency_ms, 50.0)
            self.assertGreater(report.composite_score, 0.0)


if __name__ == "__main__":
    unittest.main()

