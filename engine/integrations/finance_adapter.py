"""
engine/integrations/finance_adapter.py
In-memory Adapter wrapping the existing AutoTune Finance RAG application.
Preserves 100% of existing behavior and serves as the benchmark adapter.
"""
import os
import sys
import time
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rag_pipeline
import config as engine_config
from engine.integrations.base_adapter import BaseRAGAdapter
from engine.integrations.schemas.protocol import (
    ManifestResponse,
    ManifestCapabilities,
    ParameterSchema,
    HealthResponse,
    QueryResponse,
    QueryContext,
    QueryLatency,
    QueryUsage,
    ConfigValidationResponse,
    ConfigApplyResponse,
    ConfigRestoreResponse,
    IndexRebuildResponse
)


class FinanceRAGAdapter(BaseRAGAdapter):
    """
    Adapter for the built-in Finance RAG application.
    Supports full optimization mode (dynamic chunk size, top_k, temperature, prompt).
    """
    def __init__(self):
        self.application_name = "autotune-finance-rag"
        self.version = "1.0.0"

    def health_check(self) -> HealthResponse:
        try:
            # Check if corpus directory exists
            corpus_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpus")
            if os.path.exists(corpus_dir):
                return HealthResponse(status="healthy", message="Finance corpus accessible.")
            return HealthResponse(status="degraded", message="Finance corpus directory missing.")
        except Exception as e:
            return HealthResponse(status="unhealthy", message=str(e))

    def get_manifest(self) -> ManifestResponse:
        current_cfg = engine_config.CONFIG
        parameters = {
            "chunk_size": ParameterSchema(
                type="integer",
                default=500,
                current=current_cfg.get("chunk_size", 500),
                min=100,
                max=2000,
                step=50,
                description="Text chunk size in characters"
            ),
            "chunk_overlap": ParameterSchema(
                type="integer",
                default=50,
                current=current_cfg.get("chunk_overlap", 50),
                min=0,
                max=500,
                step=10,
                description="Overlap between adjacent chunks in characters"
            ),
            "top_k": ParameterSchema(
                type="integer",
                default=3,
                current=current_cfg.get("top_k", 3),
                min=1,
                max=15,
                step=1,
                description="Number of chunks retrieved per query"
            ),
            "temperature": ParameterSchema(
                type="float",
                default=0.0,
                current=current_cfg.get("temperature", 0.0),
                min=0.0,
                max=1.0,
                step=0.1,
                description="LLM generation sampling temperature"
            ),
            "retrieval_strategy": ParameterSchema(
                type="categorical",
                default="vector",
                current=current_cfg.get("retrieval_strategy", "vector"),
                options=["vector", "bm25", "hybrid"],
                description="Retrieval search strategy"
            )
        }
        capabilities = ManifestCapabilities(
            query=True,
            apply_config=True,
            restore_config=True,
            validate_config=True,
            rebuild_index=True,
            contexts_exposed=True,
            scores_exposed=True,
            usage_exposed=True,
            citations_exposed=True
        )
        return ManifestResponse(
            application=self.application_name,
            version=self.version,
            integration_version="2.0.0",
            mode="optimize",
            capabilities=capabilities,
            parameters=parameters,
            description="Built-in Finance RAG system indexing Indian Union Budget & tax corpus."
        )

    def get_config(self) -> Dict[str, Any]:
        return dict(engine_config.CONFIG)

    def validate_config(self, config: Dict[str, Any]) -> ConfigValidationResponse:
        errors = []
        if "chunk_size" in config:
            cs = config["chunk_size"]
            if not isinstance(cs, (int, float)) or cs < 100 or cs > 2000:
                errors.append("chunk_size must be an integer between 100 and 2000.")
        if "chunk_overlap" in config:
            co = config["chunk_overlap"]
            if not isinstance(co, (int, float)) or co < 0 or co > 500:
                errors.append("chunk_overlap must be between 0 and 500.")
        if "top_k" in config:
            tk = config["top_k"]
            if not isinstance(tk, int) or tk < 1 or tk > 15:
                errors.append("top_k must be an integer between 1 and 15.")
        if "temperature" in config:
            temp = config["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 1.0:
                errors.append("temperature must be a float between 0.0 and 1.0.")

        return ConfigValidationResponse(valid=(len(errors) == 0), errors=errors, normalized_config=config)

    def apply_config(self, config: Dict[str, Any]) -> ConfigApplyResponse:
        engine_config.CONFIG.update(config)
        return ConfigApplyResponse(success=True, active_config=dict(engine_config.CONFIG))

    def restore_config(self, config: Dict[str, Any]) -> ConfigRestoreResponse:
        engine_config.CONFIG.clear()
        engine_config.CONFIG.update(config)
        return ConfigRestoreResponse(success=True, active_config=dict(engine_config.CONFIG))

    def query(self, question: str, config_override: Optional[Dict[str, Any]] = None) -> QueryResponse:
        cfg = dict(engine_config.CONFIG)
        if config_override:
            cfg.update(config_override)

        chunk_size = int(cfg.get("chunk_size", 500))
        chunk_overlap = int(cfg.get("chunk_overlap", 50))
        top_k = int(cfg.get("top_k", 3))
        strategy = cfg.get("retrieval_strategy", "vector")
        temperature = float(cfg.get("temperature", 0.0))
        prompt_tmpl = cfg.get("prompt_template", "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:")

        # Ensure index exists
        col_name = rag_pipeline.build_index(chunk_size=chunk_size, chunk_overlap=chunk_overlap, is_experimental=False)
        corpus_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpus")
        cache_key = rag_pipeline.get_index_cache_key(chunk_size, chunk_overlap, corpus_dir)

        # Retrieval
        t_ret_start = time.time()
        chunks = rag_pipeline.retrieve(question, top_k=top_k, strategy=strategy, collection_name=col_name, cache_key=cache_key)
        ret_ms = (time.time() - t_ret_start) * 1000

        # Generation
        t_gen_start = time.time()
        ans, is_err, err_info = rag_pipeline.generate(
            query=question,
            chunks=chunks,
            prompt_template=prompt_tmpl,
            temperature=temperature,
            return_metadata=True
        )
        gen_ms = (time.time() - t_gen_start) * 1000
        total_ms = ret_ms + gen_ms

        contexts = [QueryContext(text=c) for c in chunks]
        prompt_text = prompt_tmpl.replace("{context}", "\n\n".join(chunks) if chunks else "").replace("{question}", question)
        prompt_tok = len(prompt_text) // 4
        comp_tok = len(ans) // 4

        citations = []
        if "[source:" in ans.lower() or "[source" in ans.lower():
            citations.append("budget_highlights.txt")

        return QueryResponse(
            question=question,
            answer=ans,
            contexts=contexts,
            latency=QueryLatency(
                retrieval_ms=round(ret_ms, 1),
                generation_ms=round(gen_ms, 1),
                total_ms=round(total_ms, 1)
            ),
            usage=QueryUsage(
                prompt_tokens=prompt_tok,
                completion_tokens=comp_tok,
                total_tokens=prompt_tok + comp_tok
            ),
            citations=citations,
            error=err_info.get("message") if is_err and err_info else None
        )

    def rebuild_index(self, config: Optional[Dict[str, Any]] = None) -> IndexRebuildResponse:
        cfg = config or engine_config.CONFIG
        chunk_size = int(cfg.get("chunk_size", 500))
        chunk_overlap = int(cfg.get("chunk_overlap", 50))
        col_name = rag_pipeline.build_index(chunk_size=chunk_size, chunk_overlap=chunk_overlap, is_experimental=False)
        return IndexRebuildResponse(success=True, index_id=col_name)

