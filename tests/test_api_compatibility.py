# test_api_compatibility.py
# Tests ensuring 100% backward compatibility for all existing API routes.

import sys
import os
import unittest
import json

ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "engine"))
sys.path.insert(0, ENGINE_DIR)

from fastapi.testclient import TestClient
from main import app

class TestAPICompatibility(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_get_iterations_schema(self):
        """Verify /iterations returns array with all legacy fields required by React dashboard."""
        res = self.client.get("/iterations")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 23)

        expected_fields = [
            "iteration_number", "hypothesis", "param", "old_value", "new_value",
            "old_score", "new_score", "accepted", "timestamp", "motivated_by",
            "avg_latency_ms", "total_tokens", "composite_score"
        ]
        first_row = data[0]
        for field in expected_fields:
            self.assertIn(field, first_row, f"Missing required legacy field '{field}' in /iterations response")

    def test_get_best_schema(self):
        """Verify /best returns expected dict structure for React dashboard and Streamlit app."""
        res = self.client.get("/best")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        for key in ["score", "composite_score", "avg_latency_ms", "total_tokens", "config"]:
            self.assertIn(key, data, f"Missing key '{key}' in /best response")
        self.assertIsInstance(data["config"], dict)

    def test_report_endpoint(self):
        """Verify /report/{run_id} returns markdown report download."""
        res = self.client.get("/report/current")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "text/markdown; charset=utf-8")
        self.assertIn("# 🎯 AutoTune Optimization Report", res.text)

if __name__ == "__main__":
    unittest.main()

