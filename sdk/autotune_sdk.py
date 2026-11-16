"""
sdk/autotune_sdk.py
AutoTune 2.0 Python SDK.
Allows developers to wrap any RAG pipeline (e.g. LangChain, LlamaIndex, custom functions),
declare tunable parameters, and expose the standard AutoTune REST protocol or run in-process.
"""
from typing import Callable, Dict, Any, List, Optional, Union
import time
from fastapi import FastAPI, HTTPException, Header, Depends
from engine.integrations.schemas.protocol import (
    ManifestResponse,
    ManifestCapabilities,
    ParameterSchema,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    QueryContext,
    QueryLatency,
    QueryUsage,
    ConfigValidationRequest,
    ConfigValidationResponse,
    ConfigApplyRequest,
    ConfigApplyResponse,
    ConfigRestoreRequest,
    ConfigRestoreResponse,
    IndexRebuildRequest,
    IndexRebuildResponse
)


class AutoTuneApp:
    """
    Developer-facing SDK class to register a RAG pipeline with AutoTune.
    """
    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: Optional[str] = None,
        mode: str = "optimize",  # "observe" or "optimize"
        api_key: Optional[str] = None
    ):
        self.name = name
        self.version = version
        self.description = description
        self.mode = mode
        self.api_key = api_key

        self._query_fn: Optional[Callable] = None
        self._apply_config_fn: Optional[Callable] = None
        self._validate_config_fn: Optional[Callable] = None
        self._rebuild_index_fn: Optional[Callable] = None
        self._get_config_fn: Optional[Callable] = None

        self._parameters: Dict[str, ParameterSchema] = {}
        self._current_config: Dict[str, Any] = {}
        self._capabilities = ManifestCapabilities(
            query=True,
            apply_config=(mode == "optimize"),
            restore_config=(mode == "optimize"),
            validate_config=False,
            rebuild_index=False
        )

    def register_parameter(
        self,
        name: str,
        type: str,
        default: Any,
        current: Optional[Any] = None,
        min: Optional[float] = None,
        max: Optional[float] = None,
        step: Optional[float] = None,
        options: Optional[List[Any]] = None,
        description: Optional[str] = None
    ):
        """Registers a tunable parameter with type and constraint metadata."""
        cur = current if current is not None else default
        self._parameters[name] = ParameterSchema(
            type=type,
            default=default,
            current=cur,
            min=min,
            max=max,
            step=step,
            options=options,
            description=description
        )
        self._current_config[name] = cur

    def register_query_handler(self, fn: Callable):
        """
        Registers the query handler function.
        Expected signature: fn(question: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any] or QueryResponse
        """
        self._query_fn = fn
        self._capabilities.query = True

    def register_config_handlers(
        self,
        get_config_fn: Optional[Callable] = None,
        apply_config_fn: Optional[Callable] = None,
        validate_config_fn: Optional[Callable] = None,
        rebuild_index_fn: Optional[Callable] = None
    ):
        """Registers configuration management and index rebuilding handlers."""
        if get_config_fn:
            self._get_config_fn = get_config_fn
        if apply_config_fn:
            self._apply_config_fn = apply_config_fn
            self._capabilities.apply_config = True
            self._capabilities.restore_config = True
        if validate_config_fn:
            self._validate_config_fn = validate_config_fn
            self._capabilities.validate_config = True
        if rebuild_index_fn:
            self._rebuild_index_fn = rebuild_index_fn
            self._capabilities.rebuild_index = True

    def get_manifest(self) -> ManifestResponse:
        """Returns the full AutoTune manifest."""
        current_cfg = self._get_config_fn() if self._get_config_fn else self._current_config
        # Refresh current values in parameter schemas
        for k, schema in self._parameters.items():
            if k in current_cfg:
                schema.current = current_cfg[k]

        return ManifestResponse(
            application=self.name,
            version=self.version,
            integration_version="2.0.0",
            mode=self.mode,
            capabilities=self._capabilities,
            parameters=self._parameters,
            description=self.description
        )

    def execute_query(self, question: str, config_override: Optional[Dict[str, Any]] = None) -> QueryResponse:
        """Executes a query directly in-process or via HTTP."""
        if not self._query_fn:
            raise RuntimeError("No query handler registered.")

        t_start = time.time()
        res = self._query_fn(question, config_override)
        elapsed_ms = (time.time() - t_start) * 1000

        if isinstance(res, QueryResponse):
            if res.latency is None:
                res.latency = QueryLatency(total_ms=round(elapsed_ms, 1))
            return res

        # Adapt dictionary result
        answer = res.get("answer", "")
        raw_ctx = res.get("contexts", [])
        contexts: List[QueryContext] = []
        for c in raw_ctx:
            if isinstance(c, str):
                contexts.append(QueryContext(text=c))
            elif isinstance(c, dict):
                contexts.append(QueryContext(
                    text=c.get("text", ""),
                    source=c.get("source"),
                    section=c.get("section"),
                    score=c.get("score")
                ))

        lat_info = res.get("latency")
        if isinstance(lat_info, dict):
            latency = QueryLatency(
                retrieval_ms=lat_info.get("retrieval_ms"),
                generation_ms=lat_info.get("generation_ms"),
                total_ms=lat_info.get("total_ms", round(elapsed_ms, 1))
            )
        else:
            latency = QueryLatency(total_ms=round(elapsed_ms, 1))

        usage_info = res.get("usage")
        usage = QueryUsage(**usage_info) if isinstance(usage_info, dict) else None

        citations = res.get("citations", [])

        return QueryResponse(
            question=question,
            answer=answer,
            contexts=contexts,
            latency=latency,
            usage=usage,
            citations=citations
        )

    def create_fastapi_app(self) -> FastAPI:
        """
        Creates and returns a FastAPI application exposing standard AutoTune 2.0 endpoints.
        """
        app = FastAPI(title=f"AutoTune Adapter - {self.name}", version=self.version)

        def verify_auth(authorization: Optional[str] = Header(None)):
            if self.api_key:
                if not authorization or authorization != f"Bearer {self.api_key}":
                    raise HTTPException(status_code=401, detail="Unauthorized: Invalid API key.")

        @app.get("/autotune/manifest", response_model=ManifestResponse, dependencies=[Depends(verify_auth)])
        def manifest():
            return self.get_manifest()

        @app.get("/autotune/health", response_model=HealthResponse, dependencies=[Depends(verify_auth)])
        def health():
            return HealthResponse(status="healthy", message=f"{self.name} is online.")

        @app.get("/autotune/config", dependencies=[Depends(verify_auth)])
        def get_config():
            cfg = self._get_config_fn() if self._get_config_fn else self._current_config
            return {"config": cfg}

        @app.post("/autotune/config/validate", response_model=ConfigValidationResponse, dependencies=[Depends(verify_auth)])
        def validate(req: ConfigValidationRequest):
            if self._validate_config_fn:
                valid, errors = self._validate_config_fn(req.config)
                return ConfigValidationResponse(valid=valid, errors=errors, normalized_config=req.config)
            
            # Default validation: check ranges and declared parameters
            errors = []
            for k, v in req.config.items():
                if k not in self._parameters:
                    errors.append(f"Unknown parameter '{k}'")
                    continue
                p_schema = self._parameters[k]
                if p_schema.min is not None and v < p_schema.min:
                    errors.append(f"Parameter '{k}'={v} below min {p_schema.min}")
                if p_schema.max is not None and v > p_schema.max:
                    errors.append(f"Parameter '{k}'={v} above max {p_schema.max}")
                if p_schema.options and v not in p_schema.options:
                    errors.append(f"Parameter '{k}'={v} not in allowed choices {p_schema.options}")
            return ConfigValidationResponse(valid=(len(errors) == 0), errors=errors, normalized_config=req.config)

        @app.post("/autotune/config/apply", response_model=ConfigApplyResponse, dependencies=[Depends(verify_auth)])
        def apply(req: ConfigApplyRequest):
            if self.mode == "observe" or not self._capabilities.apply_config:
                return ConfigApplyResponse(success=False, message="Application is in observe mode.")
            if self._apply_config_fn:
                success, msg = self._apply_config_fn(req.config)
                return ConfigApplyResponse(success=success, active_config=req.config, message=msg)
            self._current_config.update(req.config)
            return ConfigApplyResponse(success=True, active_config=self._current_config)

        @app.post("/autotune/config/restore", response_model=ConfigRestoreResponse, dependencies=[Depends(verify_auth)])
        def restore(req: ConfigRestoreRequest):
            if self._apply_config_fn:
                success, msg = self._apply_config_fn(req.config)
                return ConfigRestoreResponse(success=success, active_config=req.config, message=msg)
            self._current_config.update(req.config)
            return ConfigRestoreResponse(success=True, active_config=self._current_config)

        @app.post("/autotune/query", response_model=QueryResponse, dependencies=[Depends(verify_auth)])
        def query(req: QueryRequest):
            try:
                return self.execute_query(req.question, req.config_override)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/autotune/index/rebuild", response_model=IndexRebuildResponse, dependencies=[Depends(verify_auth)])
        def rebuild(req: IndexRebuildRequest):
            if not self._capabilities.rebuild_index or not self._rebuild_index_fn:
                return IndexRebuildResponse(success=False, message="Index rebuilding not supported.")
            res = self._rebuild_index_fn(req.config)
            idx_id = res.get("index_id") if isinstance(res, dict) else str(res)
            return IndexRebuildResponse(success=True, index_id=idx_id)

        return app

