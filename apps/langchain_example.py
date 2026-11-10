"""
apps/langchain_example.py
Reference example demonstrating how to integrate any LangChain or LlamaIndex RAG chain
with AutoTune 2.0 using the Python SDK.
"""
from typing import Dict, Any, Optional
from sdk.autotune_sdk import AutoTuneApp


def create_langchain_autotune_app():
    """
    Wraps a LangChain or LlamaIndex RAG pipeline in an AutoTune SDK App.
    """
    sdk_app = AutoTuneApp(
        name="langchain-enterprise-rag",
        version="2.1.0",
        mode="observe",  # Observe mode: monitors without modifying external pipeline
        description="LangChain RetrievalQA pipeline observed by AutoTune"
    )

    # Register the pipeline query executor
    def run_langchain_chain(question: str, config_override: Optional[Dict[str, Any]] = None):
        # Simulated LangChain chain invocation: result = qa_chain.invoke({"query": question})
        return {
            "question": question,
            "answer": f"LangChain synthesized response for: '{question}'",
            "contexts": [
                {"text": "Enterprise doc chunk 1 explaining corporate policy.", "source": "policy.pdf", "score": 0.89}
            ],
            "latency": {"retrieval_ms": 25.0, "generation_ms": 110.0, "total_ms": 135.0},
            "usage": {"prompt_tokens": 180, "completion_tokens": 40, "total_tokens": 220},
            "citations": ["policy.pdf"]
        }

    sdk_app.register_query_handler(run_langchain_chain)
    return sdk_app


if __name__ == "__main__":
    app = create_langchain_autotune_app().create_fastapi_app()
    import uvicorn
    print("Starting LangChain AutoTune Adapter on port 8002...")
    uvicorn.run(app, host="127.0.0.1", port=8002)

