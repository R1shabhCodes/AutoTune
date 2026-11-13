import React, { useState, useEffect } from 'react';
import { 
  X, Sliders, Play, RefreshCw, Cpu, Database, 
  RotateCcw, AlertCircle, CheckCircle2, Info, Server, ShieldAlert
} from 'lucide-react';

export default function ExperimentWizard({
  isOpen,
  onClose,
  onLaunch,
  adapters = [],
  isSystemRunning = false
}) {
  // Form State
  const [adapterId, setAdapterId] = useState('default');
  const [strategy, setStrategy] = useState('tpe'); // 'tpe' (Bayesian) | 'random'
  const [budget, setBudget] = useState(15);
  const [seed, setSeed] = useState(42);
  const [objective, setObjective] = useState('composite_score'); // 'composite_score' | 'expected_term_pass_rate' | 'avg_latency_ms'
  const [experimentName, setExperimentName] = useState('');
  
  // UI & Validation State
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Set default adapter when list loads
  useEffect(() => {
    if (adapters && adapters.length > 0 && !adapterId) {
      const active = adapters.find(a => a.is_active || a.adapter_id === 'default') || adapters[0];
      setAdapterId(active.adapter_id);
    }
  }, [adapters, adapterId]);

  // Keyboard accessibility: Close on ESC
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Selected adapter details
  const selectedAdapter = adapters.find(a => a.adapter_id === adapterId) || null;
  const isObserveMode = selectedAdapter && selectedAdapter.mode === 'observe';

  // Validation
  const validateForm = () => {
    const errs = {};
    const parsedBudget = parseInt(budget, 10);
    if (isNaN(parsedBudget) || parsedBudget < 1) {
      errs.budget = 'Trial budget must be at least 1 iteration.';
    } else if (parsedBudget > 100) {
      errs.budget = 'Trial budget cannot exceed 100 iterations.';
    }

    const parsedSeed = parseInt(seed, 10);
    if (isNaN(parsedSeed)) {
      errs.seed = 'Seed must be a valid integer.';
    }

    if (isObserveMode) {
      errs.adapter = 'Selected adapter is in observe mode and cannot be tuned.';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError(null);

    if (isSystemRunning) {
      setSubmitError('An optimization study is already in progress.');
      return;
    }

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        iterations: parseInt(budget, 10),
        adapter_id: adapterId,
        sampler_type: strategy,
        seed: parseInt(seed, 10),
        objective: objective,
        experiment_id: experimentName.trim() ? experimentName.trim() : undefined,
        project_id: 'default'
      };

      await onLaunch(payload);
      onClose();
    } catch (err) {
      setSubmitError(err.message || 'Failed to trigger optimization study.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div 
      className="console-modal-overlay" 
      role="dialog" 
      aria-modal="true" 
      aria-labelledby="wizard-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
    >
      <div className="console-modal-card wizard-modal-card">
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title-group">
            <Sliders size={18} className="panel-icon" />
            <div>
              <h3 id="wizard-modal-title" className="modal-title">
                Launch optimization experiment
              </h3>
              <span className="wizard-subtitle">
                Configure RAG target, exploration strategy, trial budget, and objective criteria.
              </span>
            </div>
          </div>
          <button 
            type="button"
            className="modal-close-btn" 
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close experiment wizard"
          >
            <X size={16} />
          </button>
        </div>

        {/* Wizard Form */}
        <form onSubmit={handleSubmit} className="wizard-form-scroll">
          {/* Section 1: Target RAG Adapter */}
          <fieldset className="wizard-fieldset">
            <legend className="wizard-legend">
              <Server size={14} />
              <span>Target RAG application</span>
            </legend>
            <p className="wizard-field-desc">
              Select which connected RAG pipeline or REST endpoint will receive candidate parameter updates.
            </p>

            <div className="wizard-adapter-grid">
              {adapters.length > 0 ? (
                adapters.map((ad) => {
                  const isSelected = ad.adapter_id === adapterId;
                  const isAdObserve = ad.mode === 'observe';
                  return (
                    <label 
                      key={ad.adapter_id} 
                      className={`wizard-card-radio ${isSelected ? 'is-selected' : ''} ${isAdObserve ? 'is-observe' : ''}`}
                    >
                      <input 
                        type="radio" 
                        name="target-adapter" 
                        value={ad.adapter_id}
                        checked={isSelected}
                        onChange={() => setAdapterId(ad.adapter_id)}
                        className="sr-only"
                      />
                      <div className="card-radio-content">
                        <div className="card-radio-header">
                          <span className="card-radio-title">
                            {ad.application || ad.name || ad.adapter_id}
                          </span>
                          <span className={`wizard-mode-pill ${isAdObserve ? 'mode-observe' : 'mode-optimize'}`}>
                            {isAdObserve ? 'Observe' : 'Optimize'}
                          </span>
                        </div>
                        <span className="card-radio-meta">
                          ID: <code className="mono-text">{ad.adapter_id}</code>
                          {ad.parameters && ` · ${ad.parameters.length} tunable parameters`}
                        </span>
                      </div>
                    </label>
                  );
                })
              ) : (
                <div className="wizard-empty-box">
                  <Info size={14} />
                  <span>Using default internal finance RAG adapter (no external endpoints registered).</span>
                </div>
              )}
            </div>

            {isObserveMode && (
              <div className="wizard-warning-box" role="alert">
                <ShieldAlert size={14} />
                <span>
                  This application is registered in observe mode. It can process evaluation queries, but candidate parameter mutations are blocked.
                </span>
              </div>
            )}
            {errors.adapter && <span className="field-error-msg">{errors.adapter}</span>}
          </fieldset>

          {/* Section 2: Optimization Strategy */}
          <fieldset className="wizard-fieldset">
            <legend className="wizard-legend">
              <Cpu size={14} />
              <span>Exploration strategy</span>
            </legend>
            <p className="wizard-field-desc">
              Choose the parameter sampling mechanism. In both modes, the local Qwen 2.5 LLM diagnostician reasons over failure distributions to bound the search space.
            </p>

            <div className="wizard-strategy-grid">
              <label className={`wizard-card-radio ${strategy === 'tpe' ? 'is-selected' : ''}`}>
                <input 
                  type="radio" 
                  name="opt-strategy" 
                  value="tpe"
                  checked={strategy === 'tpe'}
                  onChange={() => setStrategy('tpe')}
                  className="sr-only"
                />
                <div className="card-radio-content">
                  <div className="card-radio-header">
                    <span className="card-radio-title">Bayesian optimization (Optuna TPE)</span>
                    <span className="wizard-badge-recommended">Recommended</span>
                  </div>
                  <p className="card-radio-body">
                    Tree-structured Parzen Estimator builds a probabilistic model of parameter scores, focusing evaluation budget on high-yield regions.
                  </p>
                </div>
              </label>

              <label className={`wizard-card-radio ${strategy === 'random' ? 'is-selected' : ''}`}>
                <input 
                  type="radio" 
                  name="opt-strategy" 
                  value="random"
                  checked={strategy === 'random'}
                  onChange={() => setStrategy('random')}
                  className="sr-only"
                />
                <div className="card-radio-content">
                  <div className="card-radio-header">
                    <span className="card-radio-title">Random search</span>
                  </div>
                  <p className="card-radio-body">
                    Samples uniformly across the valid parameter bounds. Useful as an unbiased baseline to compare against Bayesian convergence.
                  </p>
                </div>
              </label>
            </div>
          </fieldset>

          {/* Section 3: Trial Budget & Reproducibility */}
          <fieldset className="wizard-fieldset">
            <legend className="wizard-legend">
              <Database size={14} />
              <span>Trial budget & reproducibility</span>
            </legend>
            
            <div className="wizard-grid-2col">
              <div className="wizard-input-group">
                <label htmlFor="wizard-budget-input" className="wizard-input-label">
                  Evaluation budget (trials)
                </label>
                <input 
                  id="wizard-budget-input"
                  type="number"
                  min="1"
                  max="100"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  className="wizard-text-input mono-nums"
                  aria-invalid={!!errors.budget}
                />
                <span className="wizard-help-text">
                  Total iterations to explore (includes initial baseline evaluation).
                </span>
                {errors.budget && <span className="field-error-msg">{errors.budget}</span>}
              </div>

              <div className="wizard-input-group">
                <div className="label-with-action">
                  <label htmlFor="wizard-seed-input" className="wizard-input-label">
                    Random seed
                  </label>
                  <button 
                    type="button" 
                    className="wizard-text-btn"
                    onClick={() => setSeed(Math.floor(Math.random() * 10000))}
                    title="Generate random seed"
                  >
                    <RotateCcw size={12} />
                    <span>Randomize</span>
                  </button>
                </div>
                <input 
                  id="wizard-seed-input"
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  className="wizard-text-input mono-nums"
                  aria-invalid={!!errors.seed}
                />
                <span className="wizard-help-text">
                  Deterministic seed for identical Optuna study suggestion trajectories.
                </span>
                {errors.seed && <span className="field-error-msg">{errors.seed}</span>}
              </div>
            </div>

            <div className="wizard-input-group" style={{ marginTop: 'var(--space-sm)' }}>
              <label htmlFor="wizard-exp-name" className="wizard-input-label">
                Experiment tag / name <span className="optional-tag">(optional)</span>
              </label>
              <input 
                id="wizard-exp-name"
                type="text"
                placeholder="e.g. chunk-size-tuning-v2"
                value={experimentName}
                onChange={(e) => setExperimentName(e.target.value)}
                className="wizard-text-input"
              />
              <span className="wizard-help-text">
                Human-readable identifier for audit tracking and report generation.
              </span>
            </div>
          </fieldset>

          {/* Section 4: Target Objective Focus */}
          <fieldset className="wizard-fieldset">
            <legend className="wizard-legend">
              <Sliders size={14} />
              <span>Target objective focus</span>
            </legend>
            <p className="wizard-field-desc">
              Define which evaluation metric determines whether a candidate parameter proposal is accepted.
            </p>

            <div className="wizard-objective-grid">
              <label className={`wizard-card-radio ${objective === 'composite_score' ? 'is-selected' : ''}`}>
                <input 
                  type="radio" 
                  name="target-objective" 
                  value="composite_score"
                  checked={objective === 'composite_score'}
                  onChange={() => setObjective('composite_score')}
                  className="sr-only"
                />
                <div className="card-radio-content">
                  <div className="card-radio-header">
                    <span className="card-radio-title">Balanced multi-objective</span>
                    <span className="wizard-badge-recommended">Standard</span>
                  </div>
                  <p className="card-radio-body">
                    Optimizes composite index: 60% term accuracy, 15% numerical grounding, 15% latency penalty, 10% token cost.
                  </p>
                </div>
              </label>

              <label className={`wizard-card-radio ${objective === 'expected_term_pass_rate' ? 'is-selected' : ''}`}>
                <input 
                  type="radio" 
                  name="target-objective" 
                  value="expected_term_pass_rate"
                  checked={objective === 'expected_term_pass_rate'}
                  onChange={() => setObjective('expected_term_pass_rate')}
                  className="sr-only"
                />
                <div className="card-radio-content">
                  <div className="card-radio-header">
                    <span className="card-radio-title">Accuracy-first</span>
                  </div>
                  <p className="card-radio-body">
                    Prioritizes ground-truth answer verification and factual term containment without penalizing high-token responses.
                  </p>
                </div>
              </label>

              <label className={`wizard-card-radio ${objective === 'avg_latency_ms' ? 'is-selected' : ''}`}>
                <input 
                  type="radio" 
                  name="target-objective" 
                  value="avg_latency_ms"
                  checked={objective === 'avg_latency_ms'}
                  onChange={() => setObjective('avg_latency_ms')}
                  className="sr-only"
                />
                <div className="card-radio-content">
                  <div className="card-radio-header">
                    <span className="card-radio-title">Latency-first</span>
                  </div>
                  <p className="card-radio-body">
                    Minimizes end-to-end retrieval and generation latency while enforcing strict baseline accuracy retention.
                  </p>
                </div>
              </label>
            </div>

            <div className="wizard-notice-box">
              <Info size={13} />
              <span>
                Note: Objective weighting profiles are enforced server-side by AutoTune Evaluation Engine 2.0 to ensure reproducible holdout gating.
              </span>
            </div>
          </fieldset>

          {/* Section 5: Configuration Summary */}
          <section className="wizard-summary-section" aria-label="Configuration summary">
            <span className="wizard-summary-title">Configuration summary</span>
            <div className="wizard-summary-grid">
              <div className="summary-row">
                <span className="summary-label">Target application:</span>
                <span className="summary-val">{selectedAdapter?.application || adapterId}</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Search strategy:</span>
                <span className="summary-val">
                  {strategy === 'tpe' ? 'Optuna Bayesian (TPE) + Agent Reasoning' : 'Random Exploration + Agent Reasoning'}
                </span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Planned trials:</span>
                <span className="summary-val mono-nums">{budget} iterations</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Reproducibility seed:</span>
                <span className="summary-val mono-nums">{seed}</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Primary objective:</span>
                <span className="summary-val">
                  {objective === 'composite_score' && 'Balanced Composite (Accuracy + Latency + Tokens)'}
                  {objective === 'expected_term_pass_rate' && 'Pure Accuracy (Term Pass Rate)'}
                  {objective === 'avg_latency_ms' && 'Throughput (Latency Minimization)'}
                </span>
              </div>
            </div>
          </section>

          {submitError && (
            <div className="error-callout" role="alert">
              <AlertCircle size={15} />
              <span>{submitError}</span>
            </div>
          )}

          {/* Footer Actions */}
          <div className="wizard-actions-footer">
            <button 
              type="button" 
              className="console-btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="console-btn-primary"
              disabled={isSubmitting || isObserveMode || isSystemRunning}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="animate-spin" size={14} />
                  <span>Launching…</span>
                </>
              ) : (
                <>
                  <Play size={14} />
                  <span>Launch</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
