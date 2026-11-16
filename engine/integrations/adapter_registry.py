"""
engine/integrations/adapter_registry.py
Adapter Registry for AutoTune 2.0.
Registers, resolves, and manages active RAG adapters (in-memory or remote REST).
"""
from typing import Dict, Any, Optional
from engine.integrations.base_adapter import BaseRAGAdapter
from engine.integrations.finance_adapter import FinanceRAGAdapter
from engine.integrations.rest_adapter import RestRAGAdapter


class AdapterRegistry:
    """
    Singleton registry managing connected RAG application adapters.
    """
    def __init__(self):
        self._adapters: Dict[str, BaseRAGAdapter] = {}
        # Register default finance adapter
        finance_adapter = FinanceRAGAdapter()
        self.register_adapter("finance", finance_adapter)
        self.register_adapter("default", finance_adapter)
        self._active_adapter_id: str = "default"

    def register_adapter(self, adapter_id: str, adapter: BaseRAGAdapter):
        """Registers a RAG adapter under a unique identifier."""
        self._adapters[adapter_id] = adapter

    def get_adapter(self, adapter_id: Optional[str] = None) -> BaseRAGAdapter:
        """Retrieves an adapter by ID or returns the currently active default."""
        target_id = adapter_id or self._active_adapter_id
        if target_id not in self._adapters:
            raise KeyError(f"No adapter registered with ID '{target_id}'. Registered: {list(self._adapters.keys())}")
        return self._adapters[target_id]

    def set_active_adapter(self, adapter_id: str):
        """Sets the active adapter used for optimization and evaluation."""
        if adapter_id not in self._adapters:
            raise KeyError(f"Cannot activate unregistered adapter '{adapter_id}'.")
        self._active_adapter_id = adapter_id

    def register_rest_adapter(
        self,
        adapter_id: str,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        set_active: bool = True
    ) -> RestRAGAdapter:
        """Helper to instantiate and register a remote REST adapter."""
        adapter = RestRAGAdapter(base_url=base_url, api_key=api_key, timeout=timeout)
        self.register_adapter(adapter_id, adapter)
        if set_active:
            self.set_active_adapter(adapter_id)
        return adapter

    def list_adapters(self) -> Dict[str, Dict[str, Any]]:
        """Returns metadata for all registered adapters."""
        summary = {}
        for aid, adp in self._adapters.items():
            try:
                manifest = adp.get_manifest()
                summary[aid] = {
                    "application": manifest.application,
                    "mode": manifest.mode,
                    "is_active": (aid == self._active_adapter_id),
                    "capabilities": manifest.capabilities.model_dump(),
                    "parameters": list(manifest.parameters.keys())
                }
            except Exception as e:
                summary[aid] = {
                    "application": "unknown",
                    "error": str(e),
                    "is_active": (aid == self._active_adapter_id)
                }
        return summary


# Global singleton instance
_registry_instance: Optional[AdapterRegistry] = None

def get_adapter_registry() -> AdapterRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AdapterRegistry()
    return _registry_instance

