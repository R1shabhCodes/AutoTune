import React, { useState } from 'react';
import { 
  Sparkles, ArrowRight, Zap, Database, ShieldCheck, 
  Layers, Terminal, Check, Copy, Sliders, Cpu, GitCompare, LineChart, Code2
} from 'lucide-react';

export default function LandingPage({ setActiveTab }) {
  const [copiedTab, setCopiedTab] = useState(null);
  const [activeCodeTab, setActiveCodeTab] = useState('install');

  const codeSnippets = {
    install: `# 1. Clone the repository and install requirements
git clone https://github.com/R1shabhCodes/AutoTune.git
cd AutoTune
pip install -r engine/requirements.txt`,
    integrate: `# 2. Configure your RAG pipeline hyperparameters
from engine import agent_loop, eval_harness

# Run 15 automated optimization iterations
results = agent_loop.run_optimization(iterations=15)
print(f"Optimal config found: {results['best_config']}")`,
    launch: `# 3. Launch the FastAPI server and React dashboard
python engine/main.py

# Open your browser at http://localhost:8000`
  };

  const copyCode = (tabKey) => {
    navigator.clipboard.writeText(codeSnippets[tabKey]);
    setCopiedTab(tabKey);
    setTimeout(() => setCopiedTab(null), 2000);
  };

  return (
    <div className="landing-page-container">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-badge">
          <Zap className="w-3.5 h-3.5 text-purple-400" />
          <span>AUTONOMOUS RAG HYPERPARAMETER OPTIMIZER</span>
        </div>

        <h1 className="hero-title">
          THE SELF-IMPROVING <br />
          <span className="hero-title-gradient">RAG AGENT</span>
        </h1>

        <p className="hero-subtitle">
          AutoTune formulates hypotheses, executes benchmark runs, and dynamically tunes 
          chunk size, overlap, top-k, temperature, and hybrid vector+BM25 search — maximizing accuracy 
          while minimizing latency and token costs.
        </p>

        <div className="hero-actions">
          <button 
            className="hero-btn-primary glow-btn"
            onClick={() => setActiveTab('dashboard')}
          >
            <Sparkles className="w-4 h-4" />
            <span>Launch Dashboard</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <a href="#quickstart" className="hero-btn-secondary">
            <Terminal className="w-4 h-4" />
            <span>Quickstart Guide</span>
          </a>
        </div>
      </section>

      {/* Stats Counter Grid */}
      <section className="stats-section">
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">100%</div>
            <div className="stat-label">Max Benchmark Accuracy</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">3,855+</div>
            <div className="stat-label">Document Chunks Indexed</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">70 / 20 / 10</div>
            <div className="stat-label">Multi-Objective Weight (Acc/Lat/Cost)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">&lt; 50ms</div>
            <div className="stat-label">Hybrid Vector + BM25 RRF Retrieval</div>
          </div>
        </div>
      </section>

      {/* Why AutoTune Feature Grid */}
      <section className="features-section">
        <div className="section-header">
          <h2 className="section-title">WHY AUTOTUNE?</h2>
          <p className="section-subtitle">
            Engineered for developers who want to stop guessing RAG parameters and start optimizing mathematically.
          </p>
        </div>

        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">
              <Sliders className="w-5 h-5 text-purple-400" />
            </div>
            <h3 className="feature-title">Self-Improving Learning Loop</h3>
            <p className="feature-desc">
              Autonomous LLM hypothesis formulation with mathematical score validation and automated configuration rollbacks on regression.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <Database className="w-5 h-5 text-cyan-400" />
            </div>
            <h3 className="feature-title">Hybrid Vector & BM25 Search</h3>
            <p className="feature-desc">
              Fuses dense vector embeddings (ChromaDB) with exact keyword matching (BM25) via Reciprocal Rank Fusion (RRF) for high recall.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <Cpu className="w-5 h-5 text-emerald-400" />
            </div>
            <h3 className="feature-title">Multi-Objective Optimization</h3>
            <p className="feature-desc">
              Balances Accuracy (70%), Inference Latency (20%), and Token Costs (10%) to stay strictly within production SLA budgets.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <ShieldCheck className="w-5 h-5 text-rose-400" />
            </div>
            <h3 className="feature-title">Grounding Guardrails</h3>
            <p className="feature-desc">
              Heuristic verification parser inspects numbers, percentages, and financial figures, penalizing ungrounded LLM hallucinations.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <GitCompare className="w-5 h-5 text-indigo-400" />
            </div>
            <h3 className="feature-title">Experiment History & Diffs</h3>
            <p className="feature-desc">
              MLflow-style dashboard featuring real-time loss progression curves, iteration logs, and side-by-side run comparison modals.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <Layers className="w-5 h-5 text-amber-400" />
            </div>
            <h3 className="feature-title">Universal Compatibility</h3>
            <p className="feature-desc">
              Compatible with custom Python RAG pipelines, LangChain, LlamaIndex, or containerized Docker Compose stacks out of the box.
            </p>
          </div>
        </div>
      </section>

      {/* Quickstart Code Section */}
      <section id="quickstart" className="quickstart-section">
        <div className="section-header">
          <h2 className="section-title">UP AND RUNNING IN 60 SECONDS</h2>
          <p className="section-subtitle">
            Zero configuration overhead. Start auto-tuning your pipeline with a simple command.
          </p>
        </div>

        <div className="code-block-container">
          <div className="code-header">
            <div className="code-tabs">
              <button 
                className={`code-tab ${activeCodeTab === 'install' ? 'active' : ''}`}
                onClick={() => setActiveCodeTab('install')}
              >
                <Code2 className="w-3.5 h-3.5" />
                <span>1. Setup</span>
              </button>

              <button 
                className={`code-tab ${activeCodeTab === 'integrate' ? 'active' : ''}`}
                onClick={() => setActiveCodeTab('integrate')}
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>2. Tune Engine</span>
              </button>

              <button 
                className={`code-tab ${activeCodeTab === 'launch' ? 'active' : ''}`}
                onClick={() => setActiveCodeTab('launch')}
              >
                <LineChart className="w-3.5 h-3.5" />
                <span>3. Launch UI</span>
              </button>
            </div>

            <button 
              className="copy-btn"
              onClick={() => copyCode(activeCodeTab)}
            >
              {copiedTab === activeCodeTab ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>

          <pre className="code-content">
            <code>{codeSnippets[activeCodeTab]}</code>
          </pre>
        </div>
      </section>

      {/* CTA Conversion Banner */}
      <section className="cta-section">
        <div className="cta-box">
          <h2 className="cta-title">READY TO MEET YOUR SELF-IMPROVING AGENT?</h2>
          <p className="cta-subtitle">
            Launch the interactive dashboard now to view past runs or launch a live optimization loop.
          </p>

          <button 
            className="cta-btn glow-btn"
            onClick={() => setActiveTab('dashboard')}
          >
            <span>Launch Optimizer Dashboard</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="footer-container">
        <div className="footer-top">
          <div className="footer-brand">
            <span className="footer-logo">AutoTune RAG</span>
            <p className="footer-desc">Self-improving retrieval-augmented generation pipeline optimizer.</p>
          </div>

          <div className="footer-links">
            <div className="footer-column">
              <h4>Architecture</h4>
              <span>FastAPI Backend</span>
              <span>React Dashboard</span>
              <span>ChromaDB Vector</span>
              <span>BM25 Keyword</span>
            </div>

            <div className="footer-column">
              <h4>Resources</h4>
              <a href="https://github.com/R1shabhCodes/AutoTune" target="_blank" rel="noreferrer">GitHub Repository</a>
              <a href="https://autotune-dashboard.onrender.com" target="_blank" rel="noreferrer">Render Deployment</a>
              <a href="https://rag-finance-dashboard.streamlit.app/" target="_blank" rel="noreferrer">Streamlit Chatbot</a>
            </div>
          </div>
        </div>

        <div className="footer-bottom">
          <span>© 2026 AutoTune RAG. Open-source hyperparameter optimization framework.</span>
        </div>
      </footer>
    </div>
  );
}
