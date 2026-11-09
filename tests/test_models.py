"""
Unit tests for decoupled model provider configuration, health checks, and fallback mechanisms.
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure engine is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

import models


class TestModelProviders(unittest.TestCase):

    def test_default_models(self):
        """Default optimizer is qwen2.5:1.5b and generator is llama3.2:latest."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(models.get_optimizer_model(), "qwen2.5:1.5b")
            self.assertEqual(models.get_generator_model(), "llama3.2:latest")
            self.assertEqual(models.get_ollama_base_url(), "http://localhost:11434")

    def test_env_override_models(self):
        """Environment variables override default models."""
        with patch.dict(os.environ, {
            "OPTIMIZER_MODEL": "glm-5.2:cloud",
            "GENERATOR_MODEL": "glm-5.2:cloud",
            "OLLAMA_URL": "http://127.0.0.1:11434"
        }):
            self.assertEqual(models.get_optimizer_model(), "glm-5.2:cloud")
            self.assertEqual(models.get_generator_model(), "glm-5.2:cloud")
            self.assertEqual(models.get_ollama_base_url(), "http://127.0.0.1:11434")

    def test_model_availability_matcher(self):
        """Fuzzy/prefix matching matches local Ollama model names."""
        installed = ["qwen2.5:1.5b", "llama3.2:latest", "glm-5.2:cloud"]
        avail, msg = models.check_model_availability("qwen2.5:1.5b", installed)
        self.assertTrue(avail)
        avail, msg = models.check_model_availability("llama3.2", installed)
        self.assertTrue(avail)
        avail, msg = models.check_model_availability("glm-5.2:cloud", installed)
        self.assertTrue(avail)
        avail, msg = models.check_model_availability("nonexistent:model", installed)
        self.assertFalse(avail)

    def test_provider_setup_validation(self):
        """Validation correctly assesses readiness of both models."""
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = '{"models": [{"name": "qwen2.5:1.5b"}, {"name": "llama3.2:latest"}, {"name": "glm-5.2:cloud"}]}'.encode("utf-8")
            mock_url.return_value.__enter__.return_value = mock_resp

            status = models.validate_provider_setup()
            self.assertTrue(status["ollama_available"])
            self.assertTrue(status["optimizer_ready"])
            self.assertTrue(status["generator_ready"])
            self.assertEqual(status["optimizer_model"], "qwen2.5:1.5b")
            self.assertEqual(status["generator_model"], "llama3.2:latest")


if __name__ == "__main__":
    unittest.main()
