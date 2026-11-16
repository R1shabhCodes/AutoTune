"""
engine/integrations/schemas/protocol.py
Standard Pydantic schemas for AutoTune 2.0 Universal RAG REST Protocol.
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class ParameterSchema(BaseModel):
    """Definition of a configurable parameter exposed by a RAG application."""
    type: str = Field(..., description="Parameter type: 'integer', 'float', 'string', 'boolean', 'categorical'")
    default: Any = Field(..., description="Default value")
    current: Optional[Any] = Field(None, description="Current value in the active application")
    min: Optional[float] = Field(None, description="Minimum numeric value if applicable")
    max: Optional[float] = Field(None, description="Maximum numeric value if applicable")
    step: Optional[float] = Field(None, description="Step increment for numeric exploration")
    options: Optional[List[Any]] = Field(None, description="Allowed choices for categorical parameters")
    description: Optional[str] = Field(None, description="Human-readable description of parameter purpose")


class ManifestCapabilities(BaseModel):
    """Declared capabilities supported by the RAG application."""
    query: bool = Field(True, description="Application can answer queries")
    apply_config: bool = Field(False, description="Application supports dynamic configuration updates")
    restore_config: bool = Field(False, description="Application supports reverting configuration")
    validate_config: bool = Field(False, description="Application validates configuration without applying")
    rebuild_index: bool = Field(False, description="Application supports rebuilding or switching indices")
    contexts_exposed: bool = Field(True, description="Query response contains retrieved contexts")
    scores_exposed: bool = Field(False, description="Query response contains retrieval confidence scores")
    usage_exposed: bool = Field(False, description="Query response contains token counts")
    citations_exposed: bool = Field(False, description="Query response contains citation references")


class ManifestResponse(BaseModel):
    """Manifest returned by GET /autotune/manifest."""
    application: str = Field(..., description="Name of the RAG application")
    version: str = Field("1.0.0", description="Application version")
    integration_version: str = Field("2.0.0", description="AutoTune protocol version")
    mode: str = Field("optimize", description="Supported mode: 'observe' or 'optimize'")
    capabilities: ManifestCapabilities = Field(default_factory=ManifestCapabilities)
    parameters: Dict[str, ParameterSchema] = Field(default_factory=dict)
    description: Optional[str] = Field(None, description="Brief application summary")


class HealthResponse(BaseModel):
    """Response returned by GET /autotune/health."""
    status: str = Field("healthy", description="'healthy', 'degraded', or 'unhealthy'")
    message: Optional[str] = Field(None, description="Status detail or error message")
    timestamp: Optional[str] = Field(None, description="ISO timestamp")


class QueryContext(BaseModel):
    """Individual retrieved context chunk in query response."""
    text: str = Field(..., description="Text content of the retrieved chunk")
    source: Optional[str] = Field(None, description="Source document or URI")
    section: Optional[str] = Field(None, description="Section heading or paragraph metadata")
    score: Optional[float] = Field(None, description="Similarity or retrieval score")


class QueryLatency(BaseModel):
    """Latency breakdown for query execution."""
    retrieval_ms: Optional[float] = Field(None, description="Time spent in retrieval stage")
    generation_ms: Optional[float] = Field(None, description="Time spent in LLM generation stage")
    total_ms: float = Field(..., description="Total roundtrip execution latency in milliseconds")


class QueryUsage(BaseModel):
    """Token consumption for query execution."""
    prompt_tokens: Optional[int] = Field(None, description="Input tokens")
    completion_tokens: Optional[int] = Field(None, description="Output tokens")
    total_tokens: Optional[int] = Field(None, description="Total tokens consumed")


class QueryRequest(BaseModel):
    """Request payload for POST /autotune/query."""
    question: str = Field(..., description="User query or benchmark question")
    config_override: Optional[Dict[str, Any]] = Field(None, description="Ephemeral parameter overrides for this query")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom evaluation metadata")


class QueryResponse(BaseModel):
    """Response returned by POST /autotune/query."""
    question: str = Field(..., description="Original input question")
    answer: str = Field(..., description="Generated answer text")
    contexts: List[QueryContext] = Field(default_factory=list, description="Retrieved contexts")
    latency: Optional[QueryLatency] = Field(None, description="Execution timing")
    usage: Optional[QueryUsage] = Field(None, description="Token usage statistics")
    citations: List[str] = Field(default_factory=list, description="Extracted citations or source references")
    error: Optional[str] = Field(None, description="Error description if query partially failed")


class ConfigValidationRequest(BaseModel):
    """Payload for POST /autotune/config/validate."""
    config: Dict[str, Any] = Field(..., description="Candidate configuration parameters to validate")


class ConfigValidationResponse(BaseModel):
    """Response for POST /autotune/config/validate."""
    valid: bool = Field(..., description="Whether the configuration is supported and safe")
    errors: List[str] = Field(default_factory=list, description="Validation failure details")
    normalized_config: Optional[Dict[str, Any]] = Field(None, description="Type-cast or canonical configuration")


class ConfigApplyRequest(BaseModel):
    """Payload for POST /autotune/config/apply."""
    config: Dict[str, Any] = Field(..., description="Configuration to activate in the application")


class ConfigApplyResponse(BaseModel):
    """Response for POST /autotune/config/apply."""
    success: bool = Field(..., description="Whether configuration was applied successfully")
    active_config: Dict[str, Any] = Field(default_factory=dict, description="Currently active configuration")
    message: Optional[str] = Field(None, description="Details or warning")


class ConfigRestoreRequest(BaseModel):
    """Payload for POST /autotune/config/restore."""
    config: Dict[str, Any] = Field(..., description="Previous configuration to restore")


class ConfigRestoreResponse(BaseModel):
    """Response for POST /autotune/config/restore."""
    success: bool = Field(..., description="Whether configuration was restored successfully")
    active_config: Dict[str, Any] = Field(default_factory=dict, description="Currently active configuration")
    message: Optional[str] = Field(None, description="Details or warning")


class IndexRebuildRequest(BaseModel):
    """Payload for POST /autotune/index/rebuild."""
    config: Optional[Dict[str, Any]] = Field(None, description="Indexing parameters (e.g. chunk_size, embedding_model)")


class IndexRebuildResponse(BaseModel):
    """Response for POST /autotune/index/rebuild."""
    success: bool = Field(..., description="Whether index was rebuilt or switched")
    index_id: Optional[str] = Field(None, description="Identifier of the resulting index")
    message: Optional[str] = Field(None, description="Status detail")

