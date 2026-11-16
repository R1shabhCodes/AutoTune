"""
engine/integrations/base_adapter.py
Universal BaseRAGAdapter interface for AutoTune 2.0.
Decouples AutoTune optimization and evaluation from internal pipeline implementations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from engine.integrations.schemas.protocol import (
    ManifestResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ConfigValidationResponse,
    ConfigApplyResponse,
    ConfigRestoreResponse,
    IndexRebuildResponse
)


class BaseRAGAdapter(ABC):
    """
    Abstract interface for connecting RAG applications to AutoTune 2.0.
    Subclasses can implement in-memory SDK bindings or remote REST connectors.
    """

    @abstractmethod
    def health_check(self) -> HealthResponse:
        """Checks connection and operational readiness of the target RAG application."""
        pass

    @abstractmethod
    def get_manifest(self) -> ManifestResponse:
        """Returns the application manifest, declaring capabilities and tunable parameters."""
        pass

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Returns the current active configuration of the RAG application."""
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> ConfigValidationResponse:
        """
        Validates whether a configuration is supported and safe.
        Returns valid=False with error messages if invalid.
        """
        pass

    @abstractmethod
    def apply_config(self, config: Dict[str, Any]) -> ConfigApplyResponse:
        """
        Applies a candidate configuration to the application.
        Must raise NotImplementedError or return success=False if apply_config capability is False.
        """
        pass

    @abstractmethod
    def restore_config(self, config: Dict[str, Any]) -> ConfigRestoreResponse:
        """Restores a previous configuration (e.g. after trial rejection)."""
        pass

    @abstractmethod
    def query(self, question: str, config_override: Optional[Dict[str, Any]] = None) -> QueryResponse:
        """
        Executes a query through the RAG pipeline.
        Must return answer, retrieved contexts, latency, and optional usage.
        """
        pass

    @abstractmethod
    def rebuild_index(self, config: Optional[Dict[str, Any]] = None) -> IndexRebuildResponse:
        """
        Rebuilds or switches indices if supported by the application.
        """
        pass

    def capabilities(self) -> Dict[str, bool]:
        """Convenience method returning declared capability flags."""
        manifest = self.get_manifest()
        return manifest.capabilities.model_dump()

