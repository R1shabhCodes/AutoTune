"""
engine/integrations/rest_adapter.py
REST API Connector implementing BaseRAGAdapter for remote or independently running RAG services.
Includes connection timeouts, retries, SSRF validation, API key auth, and structured error reporting.
"""
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from engine.integrations.base_adapter import BaseRAGAdapter
from engine.integrations.validation import is_safe_external_url
from engine.integrations.schemas.protocol import (
    ManifestResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
    ConfigApplyRequest,
    ConfigApplyResponse,
    ConfigRestoreRequest,
    ConfigRestoreResponse,
    IndexRebuildRequest,
    IndexRebuildResponse,
    QueryLatency,
    QueryContext,
    ManifestCapabilities
)


class RestRAGAdapter(BaseRAGAdapter):
    """
    Connects to an external RAG application over HTTP/HTTPS conforming to the AutoTune protocol.
    """
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        allow_localhost: bool = True
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.allow_localhost = allow_localhost

        # Pre-validate base URL against SSRF
        is_safe, msg = is_safe_external_url(self.base_url, allow_localhost=self.allow_localhost)
        if not is_safe:
            raise ValueError(f"Insecure endpoint URL: {msg}")

        self._cached_manifest: Optional[ManifestResponse] = None

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[float] = None
    ) -> Dict[str, Any]:
        """Executes an HTTP request with retry logic and credential protection."""
        url = f"{self.base_url}{endpoint}"
        t_out = timeout_override or self.timeout

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AutoTune-UniversalAdapter/2.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload_bytes = json.dumps(data).encode("utf-8") if data is not None else None

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, data=payload_bytes, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=t_out) as res:
                    body = res.read().decode("utf-8")
                    return json.loads(body) if body.strip() else {}
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8") if e.fp else ""
                last_error = f"HTTP {e.code}: {e.reason} - {err_body}"
                if e.code in (400, 401, 403, 404, 422):
                    # Client errors are not retried
                    break
            except urllib.error.URLError as e:
                last_error = f"Connection error: {str(e.reason)}"
            except Exception as e:
                last_error = f"Request exception: {str(e)}"

            if attempt < self.max_retries:
                time.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"REST request to {endpoint} failed after {self.max_retries + 1} attempts: {last_error}")

    def health_check(self) -> HealthResponse:
        try:
            data = self._make_request("GET", "/autotune/health")
            return HealthResponse.model_validate(data)
        except Exception as e:
            return HealthResponse(status="unhealthy", message=str(e))

    def get_manifest(self) -> ManifestResponse:
        if self._cached_manifest is not None:
            return self._cached_manifest
        data = self._make_request("GET", "/autotune/manifest")
        self._cached_manifest = ManifestResponse.model_validate(data)
        return self._cached_manifest

    def get_config(self) -> Dict[str, Any]:
        data = self._make_request("GET", "/autotune/config")
        return data.get("config", data)

    def validate_config(self, config: Dict[str, Any]) -> ConfigValidationResponse:
        manifest = self.get_manifest()
        if not manifest.capabilities.validate_config:
            # Fallback client-side validation against manifest parameters
            errors = []
            for k, v in config.items():
                if k not in manifest.parameters:
                    errors.append(f"Unknown parameter '{k}' not declared in manifest.")
            return ConfigValidationResponse(valid=(len(errors) == 0), errors=errors, normalized_config=config)

        try:
            data = self._make_request("POST", "/autotune/config/validate", data={"config": config})
            return ConfigValidationResponse.model_validate(data)
        except Exception as e:
            return ConfigValidationResponse(valid=False, errors=[str(e)])

    def apply_config(self, config: Dict[str, Any]) -> ConfigApplyResponse:
        manifest = self.get_manifest()
        if not manifest.capabilities.apply_config:
            return ConfigApplyResponse(
                success=False,
                message=f"Application '{manifest.application}' is in observe mode and does not support dynamic config updates."
            )
        data = self._make_request("POST", "/autotune/config/apply", data={"config": config})
        return ConfigApplyResponse.model_validate(data)

    def restore_config(self, config: Dict[str, Any]) -> ConfigRestoreResponse:
        manifest = self.get_manifest()
        if not manifest.capabilities.restore_config and not manifest.capabilities.apply_config:
            return ConfigRestoreResponse(success=False, message="Application does not support configuration restoration.")
        
        endpoint = "/autotune/config/restore" if manifest.capabilities.restore_config else "/autotune/config/apply"
        data = self._make_request("POST", endpoint, data={"config": config})
        return ConfigRestoreResponse(
            success=data.get("success", True),
            active_config=data.get("active_config", config),
            message=data.get("message")
        )

    def query(self, question: str, config_override: Optional[Dict[str, Any]] = None) -> QueryResponse:
        payload = {"question": question, "config_override": config_override}
        t_start = time.time()
        try:
            data = self._make_request("POST", "/autotune/query", data=payload)
            elapsed_ms = (time.time() - t_start) * 1000
            resp = QueryResponse.model_validate(data)
            if resp.latency is None:
                resp.latency = QueryLatency(total_ms=round(elapsed_ms, 1))
            return resp
        except Exception as e:
            elapsed_ms = (time.time() - t_start) * 1000
            return QueryResponse(
                question=question,
                answer="Error: Failed to query external RAG endpoint.",
                contexts=[],
                latency=QueryLatency(total_ms=round(elapsed_ms, 1)),
                error=str(e)
            )

    def rebuild_index(self, config: Optional[Dict[str, Any]] = None) -> IndexRebuildResponse:
        manifest = self.get_manifest()
        if not manifest.capabilities.rebuild_index:
            return IndexRebuildResponse(success=False, message="Application does not support index rebuilding.")
        data = self._make_request("POST", "/autotune/index/rebuild", data={"config": config})
        return IndexRebuildResponse.model_validate(data)

