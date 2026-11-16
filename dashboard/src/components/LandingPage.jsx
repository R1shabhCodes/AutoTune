import React, { useState } from 'react';
import {
  ArrowRight,
  Sliders,
  CheckCircle2,
  ShieldCheck,
  Cpu,
  Layers,
  Database,
  Terminal,
  Activity,
  GitCompare,
  Code2,
  Check,
  Copy,
  ExternalLink,
  Server,
  FileText,
  AlertTriangle,
  BarChart3,
  Search,
  Sparkles,
  Zap,
  BookOpen,
  CornerDownRight
} from 'lucide-react';

export default function LandingPage({ onNavigate }) {
  const [copiedKey, setCopiedKey] = useState(null);
  const [activeCodeTab, setActiveCodeTab] = useState('connect');

  const codeSnippets = {
    connect: `# 1. Connect any custom RAG application using the AutoTune Adapter Protocol
from engine.integrations import BaseRAGAdapter, get_adapter_registry

class ProductionRAGAdapter(BaseRAGAdapter):
    def query(self, question: str, config_override: dict = None):
        # Dispatches query through your pipeline with candidate hyperparameters
        return my_rag_service.query(question, **(config_override or {}))

registry = get_adapter_registry()
registry.register_adapter("production_rag", ProductionRAGAdapter())`,

    evaluate: `# 2. Evaluate candidate configurations against deterministic benchmark sets
from engine.eval_harness import evaluate_config

candidate_config = {
    "chunk_size": 400,
    "chunk_overlap": 40,
    "top_k": 4,
    "temperature": 0.0,
    "retrieval_strategy": "hybrid"
}

results = evaluate_config(candidate_config, is_experimental=True)
print(f"Pass Rate: {results['aggregate_score']} | Grounding: {results['grounding_rate']}")`,

    optimize: `# 3. Run multi-objective optimization with Optuna Bayesian sampling & LLM diagnosis
from engine.optimizer.hybrid_engine import HybridOptimizationEngine

engine = HybridOptimizationEngine()
await engine.run_study(
    experiment_id="exp_prod_v2",
    trial_budget=15,
    sampler_type="tpe",
    objective_spec={"primary": "composite_score", "direction": "maximize"}
)`
  };

  const copyCode = (key) => {
    navigator.clipboard.writeText(codeSnippets[key]);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="landing-root">
      {/* 1. HERO SECTION */}
      <section className="landing-hero" id="hero">
        <div className="landing-hero-badge">
          <span className="hero-status-dot" />
          <span>AutoTune 2.0 · Platform Release</span>
        </div>

        <h1 className="landing-hero-title">
          RAG Evaluation &amp; <br />
          <span className="hero-gradient-text">Optimization Platform</span>
        </h1>

        <p className="landing-hero-subtitle">
          Evaluate your RAG pipeline, identify retrieval and generation weaknesses,
          and run controlled optimization experiments using measurable evaluation results.
        </p>

        <div className="landing-hero-actions">
          <button
            className="landing-btn-primary"
            onClick={() => onNavigate('/console')}
          >
            <span>Open Console</span>
            <ArrowRight size={16} />
          </button>

          <a href="#capabilities" className="landing-btn-secondary">
            <span>Explore Features</span>
          </a>

          <a
            href="https://github.com/R1shabhCodes/AutoTune"
            target="_blank"
            rel="noopener noreferrer"
            className="landing-btn-ghost"
          >
            <Code2 size={16} />
            <span>GitHub</span>
            <ExternalLink size={12} />
          </a>
        </div>

        {/* Empirical Telemetry Bar (No 100% or invented metrics) */}
        <div className="landing-telemetry-bar">
          <div className="telemetry-pill">
            <span className="pill-label">Optimization Target</span>
            <span className="pill-value">Composite Objective (Acc / Latency / Cost)</span>
          </div>
          <div className="telemetry-pill">
            <span className="pill-label">Evaluation Engine</span>
            <span className="pill-value">Deterministic Terms + Grounding Guardrails</span>
          </div>
          <div className="telemetry-pill">
            <span className="pill-label">Exploration Method</span>
            <span className="pill-value">Bayesian TPE + Agent Diagnostic Reasoning</span>
          </div>
          <div className="telemetry-pill">
            <span className="pill-label">Integrations</span>
            <span className="pill-value">Universal Adapters (Python SDK &amp; REST)</span>
          </div>
        </div>
      </section>

      {/* 2. WHAT IS AUTOTUNE? */}
      <section className="landing-section" id="overview">
        <div className="section-meta">
          <span className="section-eyebrow">Problem Statement</span>
          <h2 className="section-heading">Why RAG Pipelines Fail Silently</h2>
          <p className="section-lead">
            Production retrieval-augmented generation systems are governed by interdependent hyperparameters
            like chunk size, overlap, retrieval depth, temperature, and hybrid fusion weights.
            Without continuous mathematical evaluation, teams operate blindly.
          </p>
        </div>

        <div className="problem-comparison-grid">
          <div className="problem-card failure-mode">
            <div className="card-badge failure">Without AutoTune · Manual Guesswork</div>
            <ul className="comparison-list">
              <li>
                <AlertTriangle size={16} className="text-bad" />
                <span><strong>Arbitrary Chunking:</strong> Relevant passages get sliced mid-sentence, causing retrieval misses.</span>
              </li>
              <li>
                <AlertTriangle size={16} className="text-bad" />
                <span><strong>Untested Retrieval Depth:</strong> Selecting top-k too shallow misses context; selecting top-k too deep injects distractors and latency.</span>
              </li>
              <li>
                <AlertTriangle size={16} className="text-bad" />
                <span><strong>Silent Hallucinations:</strong> Numbers and metrics are fabricated without automated grounding verification.</span>
              </li>
              <li>
                <AlertTriangle size={16} className="text-bad" />
                <span><strong>Unchecked Regressions:</strong> Prompt changes intended to fix one query degrade twenty other queries unnoticed.</span>
              </li>
            </ul>
          </div>

          <div className="problem-card solution-mode">
            <div className="card-badge success">With AutoTune 2.0 · Scientific Rigor</div>
            <ul className="comparison-list">
              <li>
                <CheckCircle2 size={16} className="text-ok" />
                <span><strong>Deterministic Evaluation:</strong> Every configuration is scored across exact matching, expected terms, and numerical grounding.</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="text-ok" />
                <span><strong>Multi-Objective Balance:</strong> Balances Accuracy (70%), Latency (20%), and Token Costs (10%) against SLA budgets.</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="text-ok" />
                <span><strong>Isolated Experimental Trials:</strong> Index changes run in isolated ChromaDB / BM25 namespaces to safeguard production.</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="text-ok" />
                <span><strong>Blind Holdout Gating:</strong> Promotion requires candidate configurations to beat the baseline on unseen holdout datasets.</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* 3. CORE CAPABILITIES */}
      <section className="landing-section" id="capabilities">
        <div className="section-meta">
          <span className="section-eyebrow">Architecture &amp; Features</span>
          <h2 className="section-heading">Six Core Platform Capabilities</h2>
          <p className="section-lead">
            AutoTune combines evaluation telemetry, Optuna Bayesian parameter exploration, and agentic diagnostics into one coherent platform.
          </p>
        </div>

        <div className="capabilities-grid">
          <div className="capability-card">
            <div className="cap-icon-box">
              <CheckCircle2 size={20} />
            </div>
            <h3>Multi-Metric RAG Evaluation</h3>
            <p>
              Measures generation quality with deterministic expected term pass rates, strict normalized exact match,
              numerical grounding verification, and citation presence detection.
            </p>
            <div className="cap-tags">
              <span>Term Coverage</span>
              <span>Grounding Check</span>
              <span>Citation Tracking</span>
            </div>
          </div>

          <div className="capability-card">
            <div className="cap-icon-box">
              <Activity size={20} />
            </div>
            <h3>Failure Categorization &amp; Diagnostics</h3>
            <p>
              Automatically classifies failing questions into explicit categories: missing context, ungrounded figures,
              unanswerable violations, irrelevant answers, or infrastructure timeouts.
            </p>
            <div className="cap-tags">
              <span>Diagnostic Agent</span>
              <span>Root-Cause Analysis</span>
              <span>Error Isolation</span>
            </div>
          </div>

          <div className="capability-card">
            <div className="cap-icon-box">
              <BarChart3 size={20} />
            </div>
            <h3>Controlled Experiment Tracking</h3>
            <p>
              Records immutable configuration snapshots, trial scores, latency percentiles (P50/P95), token usage,
              and optimization hypotheses into a queryable SQLite database.
            </p>
            <div className="cap-tags">
              <span>SQLite Snapshots</span>
              <span>P50 / P95 Latency</span>
              <span>Trial Audit Trail</span>
            </div>
          </div>

          <div className="capability-card">
            <div className="cap-icon-box">
              <Cpu size={20} />
            </div>
            <h3>Hybrid Optimization Engine</h3>
            <p>
              Couples Optuna Tree-structured Parzen Estimator (TPE) parameter sampling with local LLM failure reasoning,
              enforcing parameter bounds and hard SLA constraints.
            </p>
            <div className="cap-tags">
              <span>Optuna TPE</span>
              <span>Reproducible Seeds</span>
              <span>Constraint Checks</span>
            </div>
          </div>

          <div className="capability-card">
            <div className="cap-icon-box">
              <GitCompare size={20} />
            </div>
            <h3>Configuration Diff &amp; Promotion</h3>
            <p>
              Side-by-side inspection of active baseline vs candidate configurations. Candidates must satisfy blind holdout
              qualification gates before atomic promotion.
            </p>
            <div className="cap-tags">
              <span>Holdout Verification</span>
              <span>Parameter Diffs</span>
              <span>Atomic Promotion</span>
            </div>
          </div>

          <div className="capability-card">
            <div className="cap-icon-box">
              <Layers size={20} />
            </div>
            <h3>Universal RAG Adapters</h3>
            <p>
              Connect external RAG services via the standardized AutoTune protocol using an in-process Python SDK or
              SSRF-validated HTTP REST connectors in Optimize or Observe modes.
            </p>
            <div className="cap-tags">
              <span>REST Connector</span>
              <span>Python SDK</span>
              <span>Observe / Optimize</span>
            </div>
          </div>
        </div>
      </section>

      {/* 4. HOW IT WORKS */}
      <section className="landing-section" id="workflow">
        <div className="section-meta">
          <span className="section-eyebrow">End-to-End Workflow</span>
          <h2 className="section-heading">How AutoTune Optimizes Pipelines</h2>
          <p className="section-lead">
            A controlled, reproducible six-step optimization cycle executed entirely via code and verified by mathematics.
          </p>
        </div>

        <div className="workflow-steps-container">
          <div className="workflow-step">
            <div className="step-number">01</div>
            <div className="step-content">
              <h4>Connect Target Application</h4>
              <p>Register your application adapter with declared parameter schemas (chunk sizes, overlap, top-k, prompt templates).</p>
            </div>
          </div>

          <div className="workflow-step">
            <div className="step-number">02</div>
            <div className="step-content">
              <h4>Establish Measured Baseline</h4>
              <p>Execute initial evaluation against the tuning dataset to measure baseline accuracy, latency, and token consumption.</p>
            </div>
          </div>

          <div className="workflow-step">
            <div className="step-number">03</div>
            <div className="step-content">
              <h4>Diagnose Weaknesses</h4>
              <p>The diagnostic engine analyzes failing benchmark questions to isolate whether failures stem from retrieval depth or generation.</p>
            </div>
          </div>

          <div className="workflow-step">
            <div className="step-number">04</div>
            <div className="step-content">
              <h4>Generate Candidate Proposals</h4>
              <p>Optuna samples the parameter search space, constrained by diagnostic hypotheses and cross-parameter validation rules.</p>
            </div>
          </div>

          <div className="workflow-step">
            <div className="step-number">05</div>
            <div className="step-content">
              <h4>Isolated Evaluation Run</h4>
              <p>Evaluates the candidate configuration in an isolated ChromaDB / BM25 index namespace, scoring against composite objectives.</p>
            </div>
          </div>

          <div className="workflow-step">
            <div className="step-number">06</div>
            <div className="step-content">
              <h4>Promote or Reject</h4>
              <p>If composite score exceeds baseline and holdout verification passes, the champion is promoted; otherwise, it is rejected and reverted.</p>
            </div>
          </div>
        </div>
      </section>

      {/* 5. ARCHITECTURE OVERVIEW */}
      <section className="landing-section" id="architecture">
        <div className="section-meta">
          <span className="section-eyebrow">System Architecture</span>
          <h2 className="section-heading">Decoupled Monorepo Architecture</h2>
          <p className="section-lead">
            Engineered with strict separation of concerns between optimization, evaluation, storage, and consumer applications.
          </p>
        </div>

        <div className="architecture-diagram-card">
          <div className="arch-layer">
            <div className="arch-layer-header">
              <span className="layer-tag">Layer 1</span>
              <h4>Presentation &amp; Observability</h4>
            </div>
            <div className="arch-nodes">
              <div className="arch-node">React 18 Dashboard (Hallmark Console)</div>
              <div className="arch-node">FastAPI Streaming WebSocket (/ws)</div>
              <div className="arch-node">Streamlit Finance Chatbot Demo</div>
            </div>
          </div>

          <div className="arch-connector">
            <CornerDownRight size={16} />
            <span>FastAPI REST APIs &amp; Live WebSocket Telemetry</span>
          </div>

          <div className="arch-layer">
            <div className="arch-layer-header">
              <span className="layer-tag">Layer 2</span>
              <h4>AutoTune Core Engine</h4>
            </div>
            <div className="arch-nodes">
              <div className="arch-node highlight">HybridOptimizationEngine (Optuna TPE)</div>
              <div className="arch-node highlight">EvaluationService 2.0</div>
              <div className="arch-node highlight">AgentDiagnostician (Qwen / Gemini)</div>
              <div className="arch-node highlight">PromotionManager &amp; Diffs</div>
            </div>
          </div>

          <div className="arch-connector">
            <CornerDownRight size={16} />
            <span>BaseRAGAdapter Protocol (Universal REST &amp; Python SDK)</span>
          </div>

          <div className="arch-layer">
            <div className="arch-layer-header">
              <span className="layer-tag">Layer 3</span>
              <h4>Retrieval, Storage &amp; Inference</h4>
            </div>
            <div className="arch-nodes">
              <div className="arch-node">SQLite 3 (Immutable Trial Snapshots)</div>
              <div className="arch-node">ChromaDB (Isolated Collection Namespaces)</div>
              <div className="arch-node">Rank-BM25 (Reciprocal Rank Fusion)</div>
              <div className="arch-node">Ollama Daemon / Gemini API Fallback</div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. CODE & INTEGRATION GUIDE */}
      <section className="landing-section" id="code">
        <div className="section-meta">
          <span className="section-eyebrow">Developer SDK</span>
          <h2 className="section-heading">Integration in Three Steps</h2>
          <p className="section-lead">
            Use the in-process Python SDK or REST protocol to integrate AutoTune into your existing pipelines.
          </p>
        </div>

        <div className="code-card">
          <div className="code-card-header">
            <div className="code-tabs">
              <button
                className={`code-tab ${activeCodeTab === 'connect' ? 'active' : ''}`}
                onClick={() => setActiveCodeTab('connect')}
              >
                <span>1. Connect Adapter</span>
              </button>
              <button
                className={`code-tab ${activeCodeTab === 'evaluate' ? 'active' : ''}`}
                onClick={() => setActiveCodeTab('evaluate')}
              >
                <span>2. Evaluate Config</span>
              </button>
              <button
                className={`code-tab ${activeCodeTab === 'optimize' ? 'active' : ''}`}
                onClick={() => setActiveCodeTab('optimize')}
              >
                <span>3. Run Optimizer</span>
              </button>
            </div>

            <button
              className="code-copy-btn"
              onClick={() => copyCode(activeCodeTab)}
              title="Copy code"
            >
              {copiedKey === activeCodeTab ? (
                <>
                  <Check size={14} className="text-ok" />
                  <span className="text-ok">Copied</span>
                </>
              ) : (
                <>
                  <Copy size={14} />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>

          <pre className="code-card-body">
            <code>{codeSnippets[activeCodeTab]}</code>
          </pre>
        </div>
      </section>

      {/* 7. TECHNICAL STACK & INFERENCE OPTIONS */}
      <section className="landing-section" id="stack">
        <div className="section-meta">
          <span className="section-eyebrow">Specifications</span>
          <h2 className="section-heading">Supported Stack &amp; Inference</h2>
        </div>

        <div className="tech-spec-grid">
          <div className="spec-card">
            <h4>Inference Providers</h4>
            <ul>
              <li><strong>Local Offline:</strong> Ollama daemon (defaults to <code>qwen2.5:1.5b</code> optimizer and <code>llama3.2:latest</code> generator).</li>
              <li><strong>Cloud Fallback:</strong> Google Gemini API via <code>GEMINI_API_KEY</code> for CI/CD and deployment without local GPUs.</li>
              <li><strong>Non-Blocking Boot:</strong> Provider health checks use short timeouts; backend never crashes if Ollama is offline.</li>
            </ul>
          </div>

          <div className="spec-card">
            <h4>Retrieval &amp; Search</h4>
            <ul>
              <li><strong>Vector Search:</strong> ChromaDB persistent collections with SHA256 corpus fingerprinting.</li>
              <li><strong>Sparse Keyword:</strong> BM25 Okapi with whitespace and token normalization.</li>
              <li><strong>Hybrid RRF:</strong> Reciprocal Rank Fusion fuses dense and sparse results.</li>
              <li><strong>Low-RAM Mode:</strong> <code>AUTOTUNE_DISABLE_EMBEDDINGS=1</code> operates in pure BM25 mode under 512 MB RAM.</li>
            </ul>
          </div>

          <div className="spec-card">
            <h4>Storage &amp; State</h4>
            <ul>
              <li><strong>Database:</strong> SQLite 3 with WAL mode, busy timeout, and schema migrations.</li>
              <li><strong>State Isolation:</strong> Immutable JSON snapshots registered per trial.</li>
              <li><strong>Safety:</strong> Rejected configurations are never promoted or returned as champions.</li>
            </ul>
          </div>

          <div className="spec-card">
            <h4>Frontend Console</h4>
            <ul>
              <li><strong>Design System:</strong> Hallmark Console (Graphite, Host Grotesk, Atkinson Hyperlegible Mono).</li>
              <li><strong>Framework:</strong> React 18, Vite 5, Recharts, Lucide Icons.</li>
              <li><strong>Routing:</strong> Client-side SPA routing with instant progressive loading.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* 8. PROJECT LIMITATIONS & CAPABILITIES */}
      <section className="landing-section" id="limitations">
        <div className="section-meta">
          <span className="section-eyebrow">Honest Engineering</span>
          <h2 className="section-heading">Current Scope &amp; Known Limitations</h2>
          <p className="section-lead">
            AutoTune is engineered as an empirical optimization tool. Here is what is genuinely supported and what is out of scope.
          </p>
        </div>

        <div className="limitations-grid">
          <div className="limitation-item supported">
            <span className="lim-badge ok">Supported</span>
            <h5>Mathematical Decision Rule</h5>
            <p>Optimization is strictly deterministic: candidate configurations are rejected if they do not outperform the baseline composite score.</p>
          </div>

          <div className="limitation-item supported">
            <span className="lim-badge ok">Supported</span>
            <h5>Offline Resilience</h5>
            <p>The console and static landing page load fully even when inference engines (Ollama) are completely offline or unreachable.</p>
          </div>

          <div className="limitation-item constraint">
            <span className="lim-badge note">Constraint</span>
            <h5>Inference Availability</h5>
            <p>Running active LLM proposals requires either a running local Ollama instance or a configured <code>GEMINI_API_KEY</code>.</p>
          </div>

          <div className="limitation-item constraint">
            <span className="lim-badge note">Constraint</span>
            <h5>Render Free 512 MB RAM</h5>
            <p>Render Free instances enforce a 512 MB memory limit. Eager embedding loading is disabled; BM25 mode is recommended for free instances.</p>
          </div>
        </div>
      </section>

      {/* 9. BOTTOM CTA BANNER */}
      <section className="landing-cta-banner">
        <div className="cta-banner-content">
          <span className="cta-pill">Ready to Explore</span>
          <h2>Launch the AutoTune Console</h2>
          <p>Inspect historical trial records, benchmark telemetry, and active RAG adapter manifests.</p>
          <div className="cta-actions">
            <button
              className="landing-btn-primary glow-btn"
              onClick={() => onNavigate('/console')}
            >
              <span>Open Developer Console</span>
              <ArrowRight size={16} />
            </button>
            <a
              href="https://github.com/R1shabhCodes/AutoTune"
              target="_blank"
              rel="noopener noreferrer"
              className="landing-btn-secondary"
            >
              <Code2 size={16} />
              <span>View Source on GitHub</span>
            </a>
          </div>
        </div>
      </section>

      {/* 10. FOOTER */}
      <footer className="landing-footer">
        <div className="footer-top-row">
          <div className="footer-brand-col">
            <div className="footer-logo">
              <Terminal size={18} className="text-accent" />
              <span>AutoTune 2.0</span>
            </div>
            <p className="footer-tagline">
              Universal RAG evaluation, observability, and hyperparameter optimization platform.
            </p>
          </div>

          <div className="footer-links-grid">
            <div className="footer-col">
              <h5>Navigation</h5>
              <button onClick={() => onNavigate('/')}>Home</button>
              <button onClick={() => onNavigate('/console')}>Console</button>
              <button onClick={() => onNavigate('/console/overview')}>Overview</button>
              <button onClick={() => onNavigate('/console/experiments')}>Live Monitor</button>
            </div>

            <div className="footer-col">
              <h5>Platform</h5>
              <button onClick={() => onNavigate('/console/applications')}>Applications</button>
              <button onClick={() => onNavigate('/console/evaluations')}>Evaluation Analytics</button>
              <button onClick={() => onNavigate('/console/trials')}>Trial History</button>
              <button onClick={() => onNavigate('/console/promotions')}>Promotions &amp; Diffs</button>
            </div>

            <div className="footer-col">
              <h5>Resources</h5>
              <a href="https://github.com/R1shabhCodes/AutoTune" target="_blank" rel="noopener noreferrer">
                GitHub Repository
              </a>
              <a href="https://autotune-dashboard.onrender.com" target="_blank" rel="noopener noreferrer">
                Render Deployment
              </a>
              <a href="https://rag-finance-dashboard.streamlit.app" target="_blank" rel="noopener noreferrer">
                Streamlit Demo
              </a>
            </div>
          </div>
        </div>

        <div className="footer-bottom-row">
          <span>&copy; 2026 AutoTune. Monorepo open-source RAG optimization platform.</span>
          <span className="footer-mono">v2.0.0 · Python 3 / FastAPI / React 18</span>
        </div>
      </footer>
    </div>
  );
}
