# app.py
# Streamlit chat UI for the RAG-Finance chatbot.
# Run with: streamlit run app.py

import streamlit as st
import json
import rag_pipeline as rag

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Finance Chatbot",
    page_icon="💰",
    layout="wide",
)

# ── Custom styling ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
    
    .main-header h1 {
        color: #e2e8f0;
        font-size: 2rem;
        margin: 0;
    }
    
    .main-header p {
        color: #94a3b8;
        margin: 0.5rem 0 0 0;
    }
    
    .source-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        color: #cbd5e1;
        font-size: 0.85rem;
    }
    
    .source-label {
        color: #818cf8;
        font-weight: 600;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .config-badge {
        background: #1e1b4b;
        color: #a5b4fc;
        padding: 0.25rem 0.75rem;
        border-radius: 8px;
        font-size: 0.8rem;
        display: inline-block;
        margin: 0.2rem;
        border: 1px solid #312e81;
    }
    
    .answer-box {
        background: linear-gradient(135deg, #0f172a, #1e293b);
        border: 1px solid #6366f1;
        border-radius: 12px;
        padding: 1.5rem;
        color: #e2e8f0;
        line-height: 1.7;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar: Config display ─────────────────────────────────────────────────
def show_sidebar():
    st.sidebar.markdown("## ⚙️ RAG Configuration")
    config = rag.load_config()
    
    st.sidebar.markdown("**Current Settings:**")
    st.sidebar.code(json.dumps(config, indent=2), language="json")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 How It Works")
    st.sidebar.markdown("""
    1. Your question is **embedded** into a vector
    2. **Top-K** most relevant chunks are retrieved from the corpus  
    3. Chunks + question are sent to **Ollama (llama3.2)** for generation
    4. Use **AutoTune** (`d:/AutoTune`) to optimize these settings!
    """)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📁 Corpus Files")
    import glob, os
    txt_files = sorted(glob.glob(os.path.join(rag.CORPUS_DIR, "*.txt")))
    for f in txt_files:
        name = os.path.basename(f)
        size_kb = os.path.getsize(f) / 1024
        st.sidebar.markdown(f"- 📄 `{name}` ({size_kb:.1f} KB)")

    return config


# ── Main UI ──────────────────────────────────────────────────────────────────
def main():
    config = show_sidebar()

    # Header
    st.markdown("""
    <div class="main-header">
        <h1>💰 RAG Finance Chatbot</h1>
        <p>Ask questions about Indian Income Tax, GST, Mutual Funds, RBI Policy & Budget 2024</p>
    </div>
    """, unsafe_allow_html=True)

    # Initialize index on first run
    if "index_built" not in st.session_state:
        with st.spinner("🔨 Building vector index from corpus..."):
            rag.build_index(
                chunk_size=int(config["chunk_size"]),
                chunk_overlap=int(config["chunk_overlap"]),
            )
            st.session_state.index_built = True
            st.session_state.messages = []

    # Show config badges
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Chunk Size", config["chunk_size"])
    col2.metric("Chunk Overlap", config["chunk_overlap"])
    col3.metric("Top-K", config["top_k"])
    col4.metric("Temperature", config["temperature"])

    st.markdown("---")

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                st.markdown(f"""<div class="answer-box">{msg['content']}</div>""", unsafe_allow_html=True)
                if "sources" in msg and msg["sources"]:
                    with st.expander("📚 Sources Used", expanded=False):
                        for i, source in enumerate(msg["sources"]):
                            st.markdown(f"**[{i+1}] {source['source']}, Section: {source.get('section', 'N/A')} (Paragraph {source.get('paragraph_index', 0) + 1})**")
                            if source.get('distance') is not None:
                                st.markdown(f"*Distance: {source['distance']:.4f}*")
                            st.info(source["text"])
                            st.markdown("---")

    # Chat input
    if prompt := st.chat_input("Ask a finance question... (e.g., 'What is Section 80C?')"):
        # Show user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate answer
        with st.chat_message("assistant"):
            with st.spinner("🔍 Retrieving and generating..."):
                result = rag.query(prompt, config)

            # Display answer
            st.markdown(f"""<div class="answer-box">{result['answer']}</div>""", unsafe_allow_html=True)

            # Display sources
            with st.expander("📚 Sources Used", expanded=False):
                for i, source in enumerate(result["sources"]):
                    st.markdown(f"**[{i+1}] {source['source']}, Section: {source.get('section', 'N/A')} (Paragraph {source.get('paragraph_index', 0) + 1})**")
                    if source.get('distance') is not None:
                        st.markdown(f"*Distance: {source['distance']:.4f}*")
                    st.info(source["text"])
                    st.markdown("---")

            # Build response for history
            st.session_state.messages.append({
                "role": "assistant",
                "content": result['answer'],
                "sources": result['sources']
            })

    # Sample questions
    st.markdown("---")
    st.markdown("### 💡 Try These Questions")
    sample_qs = [
        "What is Section 80C and what is the deduction limit?",
        "What are the GST tax slabs in India?",
        "What is the current repo rate set by RBI?",
        "What is the lock-in period for ELSS mutual funds?",
        "What changes were made to capital gains tax in Budget 2024?",
        "How does Input Tax Credit work in GST?",
    ]
    cols = st.columns(2)
    for i, q in enumerate(sample_qs):
        cols[i % 2].markdown(f"- {q}")


if __name__ == "__main__":
    main()
