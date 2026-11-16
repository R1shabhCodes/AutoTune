"""
engine/integrations/__init__.py
AutoTune 2.0 Integrations Architecture.
Decouples optimization and evaluation from internal RAG implementations.
"""
from engine.integrations.base_adapter import BaseRAGAdapter
from engine.integrations.rest_adapter import RestRAGAdapter
from engine.integrations.finance_adapter import FinanceRAGAdapter
from engine.integrations.adapter_registry import AdapterRegistry, get_adapter_registry
from engine.integrations.validation import is_safe_external_url

__all__ = [
    "BaseRAGAdapter",
    "RestRAGAdapter",
    "FinanceRAGAdapter",
    "AdapterRegistry",
    "get_adapter_registry",
    "is_safe_external_url"
]

