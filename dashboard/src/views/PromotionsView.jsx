import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck, AlertTriangle, CheckCircle2, XCircle, ArrowRight,
  RefreshCw, Rocket, Lock, Info, Server, HelpCircle, AlertCircle
} from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import EmptyState from '../components/common/EmptyState';
import ConfigurationDiff from '../components/promotion/ConfigurationDiff';
import { api } from '../api/client';

export default function PromotionsView({
  bestConfig = null,
  holdoutScore = null,
  adapters = [],
  onRefresh = null
}) {
  const [selectedAdapterId, setSelectedAdapterId] = useState('default');
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState(null);
  const [evalError, setEvalError] = useState(null);

  const [confirmChecked, setConfirmChecked] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [promoteResult, setPromoteResult] = useState(null);
  const [promoteError, setPromoteError] = useState(null);

  // Active target adapter
  const activeAdapter = adapters.find(a => a.adapter_id === selectedAdapterId) || adapters[0] || null;
  const isObserveMode = activeAdapter?.mode === 'observe';

  // Candidate and Baseline configurations
  const baselineConfig = bestConfig?.baseline_config || bestConfig?.config || {};
  const candidateConfig = bestConfig?.candidate_config || bestConfig?.config || {};

  const hasChampion = bestConfig && bestConfig.iteration_number !== undefined && bestConfig.iteration_number !== null;
  const isIdentical = JSON.stringify(baselineConfig) === JSON.stringify(candidateConfig);

  // Run Holdout Gate Evaluation
  const handleEvaluate = async () => {
    setEvaluating(true);
    setEvalError(null);
    setEvalResult(null);
    setPromoteResult(null);
    setPromoteError(null);

    try {
      const payload = {
        candidate_config: candidateConfig,
        baseline_config: baselineConfig,
        adapter_id: selectedAdapterId
      };
      const res = await api.evaluatePromotion(payload);
      setEvalResult(res);
    } catch (err) {
      console.error('Promotion evaluation error:', err);
      setEvalError(err.message || 'Failed to complete holdout evaluation gate.');
    } finally {
      setEvaluating(false);
    }
  };

  // Run Explicit Promotion
  const handlePromote = async () => {
    if (!confirmChecked || promoting) return;

    setPromoting(true);
    setPromoteError(null);
    setPromoteResult(null);

    try {
      const payload = {
        candidate_config: candidateConfig,
        adapter_id: selectedAdapterId
      };
      const res = await api.promoteConfig(payload);
      if (res.status === 'failed') {
        setPromoteError(res.message || 'Promotion rejected by application adapter.');
      } else {
        setPromoteResult({
          status: 'promoted',
          timestamp: new Date().toLocaleTimeString(),
          active_config: res.active_config,
          message: res.message || 'Configuration successfully activated in production.'
        });
        setConfirmChecked(false);
        if (onRefresh) {
          onRefresh();
        }
      }
    } catch (err) {
      console.error('Promotion action error:', err);
      setPromoteError(err.message || 'Network or server error executing promotion.');
    } finally {
      setPromoting(false);
    }
  };

  return (
    <div className="promotions-view-root">
      {/* 1. Page Header */}
      <div className="page-header-block">
        <div className="page-title-group">
          <div className="page-title-row">
            <ShieldCheck size={18} style={{ color: 'var(--color-sage)' }} />
            <h1 className="page-title">Promotion and configuration diff</h1>
          </div>
          <p className="page-subtitle">
            Inspect the optimization champion against the active production configuration, verify blind holdout qualification, and promote verified parameters.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
          {onRefresh && (
            <button
              type="button"
              className="console-btn-wizard"
              onClick={onRefresh}
              title="Refresh telemetry"
            >
              <RefreshCw size={12} />
              <span>Refresh</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Top Status Cards */}
      <div className="promotions-kpi-grid">
        <section className="console-panel promo-stat-card" aria-label="Champion study status">
          <div className="promo-stat-header">
            <span className="promo-stat-label">Optimization champion</span>
            <StatusBadge
              status={hasChampion ? 'accepted' : 'idle'}
              label={hasChampion ? 'Champion identified' : 'Baseline active'}
            />
          </div>
          <div className="promo-stat-main">
            <span className="promo-stat-val mono-nums">
              {hasChampion ? `Trial #${bestConfig.iteration_number}` : 'None'}
            </span>
            <span className="promo-stat-sub mono-nums">
              {bestConfig?.experiment_id || 'No active study'}
            </span>
          </div>
        </section>

        <section className="console-panel promo-stat-card" aria-label="Score performance">
          <div className="promo-stat-header">
            <span className="promo-stat-label">Composite champion score</span>
            <span className="promo-stat-tag mono-nums">
              Accuracy: {bestConfig?.score ? (bestConfig.score * 100).toFixed(1) + '%' : '0.0%'}
            </span>
          </div>
          <div className="promo-stat-main">
            <span className="promo-stat-val mono-nums" style={{ color: 'var(--color-cool)' }}>
              {typeof bestConfig?.composite_score === 'number' ? bestConfig.composite_score.toFixed(4) : (bestConfig?.score ? bestConfig.score.toFixed(4) : '0.0000')}
            </span>
            <span className="promo-stat-sub">
              Latency: {bestConfig?.avg_latency_ms ? bestConfig.avg_latency_ms.toFixed(0) + 'ms' : '0ms'}
            </span>
          </div>
        </section>

        <section className="console-panel promo-stat-card" aria-label="Holdout qualification score">
          <div className="promo-stat-header">
            <span className="promo-stat-label">Blind holdout score</span>
            <StatusBadge
              status={holdoutScore !== null ? 'healthy' : 'idle'}
              label={holdoutScore !== null ? 'Evaluated' : 'Unchecked'}
            />
          </div>
          <div className="promo-stat-main">
            <span className="promo-stat-val mono-nums" style={{ color: 'var(--color-sage)' }}>
              {holdoutScore !== null ? holdoutScore.toFixed(4) : '---'}
            </span>
            <span className="promo-stat-sub">
              Anti-overfitting validation partition
            </span>
          </div>
        </section>

        <section className="console-panel promo-stat-card" aria-label="Target RAG application">
          <div className="promo-stat-header">
            <span className="promo-stat-label">Target application</span>
            <StatusBadge
              status={isObserveMode ? 'degraded' : 'healthy'}
              label={isObserveMode ? 'Observe mode' : 'Optimize mode'}
            />
          </div>
          <div className="promo-stat-main">
            <span className="promo-stat-val" style={{ fontSize: 'var(--text-md)', fontWeight: 600 }}>
              {activeAdapter?.application || activeAdapter?.name || 'Finance RAG (Internal)'}
            </span>
            <span className="promo-stat-sub mono-nums">
              Adapter ID: {activeAdapter?.adapter_id || selectedAdapterId}
            </span>
          </div>
        </section>
      </div>

      {/* 3. Observe Mode Limitation Callout */}
      {isObserveMode && (
        <div className="app-limitation-notice" role="alert">
          <Lock size={15} style={{ flexShrink: 0 }} />
          <div>
            <strong>Observe mode active: </strong>
            Application adapter <code>{activeAdapter?.adapter_id}</code> does not permit dynamic configuration mutation. You may evaluate promotion qualification, but parameter changes cannot be applied over HTTP until <code>apply_config: true</code> is declared by the external service.
          </div>
        </div>
      )}

      {/* 4. Configuration Diff Component */}
      <ConfigurationDiff
        baselineConfig={baselineConfig}
        candidateConfig={candidateConfig}
        baselineMetrics={bestConfig ? { composite_score: bestConfig.score || 0.7, score: bestConfig.score || 0.7, avg_latency_ms: bestConfig.avg_latency_ms || 320 } : null}
        candidateMetrics={bestConfig ? { composite_score: bestConfig.composite_score || bestConfig.score || 0.7, score: bestConfig.score || 0.7, avg_latency_ms: bestConfig.avg_latency_ms || 320 } : null}
        title="Active vs Champion configuration differential"
      />

      {/* 5. Two-Step Promotion Gate Workflow */}
      <div className="promotion-gate-container">
        {/* Step A: Blind Holdout Qualification Gate */}
        <section className="console-panel promo-step-panel" aria-label="Holdout qualification verification">
          <div className="step-panel-header">
            <div>
              <h3 className="step-heading">Holdout qualification gate</h3>
              <p className="step-subheading">
                Verifies that candidate parameter modifications do not degrade accuracy on the protected blind holdout partition.
              </p>
            </div>
          </div>

          <div className="step-body">
            {evalError && (
              <div className="error-callout" role="alert">
                <AlertCircle size={14} />
                <span>{evalError}</span>
              </div>
            )}

            {evalResult && (
              <div className={`eval-result-card ${evalResult.eligible_for_promotion ? 'is-approved' : 'is-rejected'}`}>
                <div className="eval-result-top">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2xs)' }}>
                    {evalResult.eligible_for_promotion ? (
                      <CheckCircle2 size={16} style={{ color: 'var(--color-ok)' }} />
                    ) : (
                      <XCircle size={16} style={{ color: 'var(--color-bad)' }} />
                    )}
                    <span className="eval-result-verdict">
                      {evalResult.eligible_for_promotion ? 'Qualification approved' : 'Qualification rejected'}
                    </span>
                  </div>
                  <StatusBadge
                    status={evalResult.eligible_for_promotion ? 'healthy' : 'rejected'}
                    label={evalResult.eligible_for_promotion ? 'Eligible' : 'Blocked'}
                  />
                </div>

                <p className="eval-result-recommendation">
                  {evalResult.recommendation}
                </p>

                {evalResult.holdout_results && (
                  <div className="eval-score-comparison-strip">
                    <div className="eval-score-item">
                      <span className="eval-score-lbl">Baseline holdout</span>
                      <span className="eval-score-num mono-nums">
                        {evalResult.holdout_results.baseline_score?.toFixed(4) ?? '0.0000'}
                      </span>
                    </div>
                    <ArrowRight size={13} style={{ color: 'var(--color-muted)' }} />
                    <div className="eval-score-item">
                      <span className="eval-score-lbl">Candidate holdout</span>
                      <span className="eval-score-num mono-nums" style={{ color: evalResult.holdout_results.passed ? 'var(--color-ok)' : 'var(--color-bad)' }}>
                        {evalResult.holdout_results.candidate_score?.toFixed(4) ?? '0.0000'}
                      </span>
                    </div>
                    <div className="eval-score-item" style={{ marginLeft: 'auto' }}>
                      <span className="eval-score-lbl">Gate outcome</span>
                      <span className={`eval-gate-text ${evalResult.holdout_results.passed ? 'pass' : 'fail'}`}>
                        {evalResult.holdout_results.passed ? 'No holdout regression' : 'Degraded holdout accuracy'}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="step-actions">
              <button
                type="button"
                className="console-btn-wizard text-nowrap"
                onClick={handleEvaluate}
                disabled={evaluating || isIdentical}
                title={isIdentical ? 'Candidate is identical to baseline' : 'Evaluate candidate against holdout set'}
              >
                {evaluating ? (
                  <>
                    <RefreshCw size={12} className="animate-spin" />
                    <span>Evaluating…</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck size={12} />
                    <span>Run gate</span>
                  </>
                )}
              </button>

              {isIdentical && (
                <span className="step-hint">
                  Baseline and candidate configurations are currently identical.
                </span>
              )}
            </div>
          </div>
        </section>

        {/* Step B: Explicit Production Promotion */}
        <section className="console-panel promo-step-panel" aria-label="Production promotion action">
          <div className="step-panel-header">
            <div>
              <h3 className="step-heading">Production promotion action</h3>
              <p className="step-subheading">
                Applies the verified parameter modifications directly to the active RAG adapter.
              </p>
            </div>
          </div>

          <div className="step-body">
            {promoteError && (
              <div className="error-callout" role="alert">
                <AlertCircle size={14} />
                <span>{promoteError}</span>
              </div>
            )}

            {promoteResult && (
              <div className="app-connect-success" role="status">
                <CheckCircle2 size={15} style={{ color: 'var(--color-ok)' }} />
                <div>
                  <strong>Promotion confirmed at {promoteResult.timestamp}: </strong>
                  <span>{promoteResult.message}</span>
                </div>
              </div>
            )}

            {/* Holdout warning if promoting without evaluation */}
            {!evalResult && !isIdentical && (
              <div className="promo-warning-box" role="alert">
                <AlertTriangle size={14} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
                <span>
                  Holdout qualification has not been run for this candidate. Evaluating holdout performance in Step 1 is strongly recommended before activating parameters in production.
                </span>
              </div>
            )}

            {/* Informational callout if candidate and baseline are already identical */}
            {isIdentical && (
              <div className="promo-warning-box" style={{ background: 'var(--color-paper-1)', borderColor: 'var(--color-rule)' }} role="status">
                <CheckCircle2 size={14} style={{ color: 'var(--color-sage)', flexShrink: 0 }} />
                <span>
                  <strong>Configuration in sync:</strong> Champion parameters already match the active production baseline. Run a new experiment in the Trial Workspace or Wizard to propose new parameter values before promoting.
                </span>
              </div>
            )}

            {/* Confirmation checkbox */}
            <div>
              <label
                className="promo-confirm-checkbox-label"
                style={{ opacity: (isObserveMode || promoting || isIdentical) ? 0.6 : 1, cursor: (isObserveMode || promoting || isIdentical) ? 'not-allowed' : 'pointer' }}
              >
                <input
                  type="checkbox"
                  checked={confirmChecked}
                  onChange={e => setConfirmChecked(e.target.checked)}
                  disabled={isObserveMode || promoting || isIdentical}
                />
                <span>
                  I confirm that I have reviewed the parameter differential and authorize applying these values to the active production adapter.
                </span>
              </label>
              {isIdentical && (
                <p style={{ margin: 'var(--space-2xs) 0 0 calc(16px + var(--space-xs))', fontSize: 'var(--text-2xs)', color: 'var(--color-muted)' }}>
                  Checkbox locked: Candidate parameters already match active production values (0 changes to apply).
                </p>
              )}
              {isObserveMode && (
                <p style={{ margin: 'var(--space-2xs) 0 0 calc(16px + var(--space-xs))', fontSize: 'var(--text-2xs)', color: 'var(--color-accent)' }}>
                  Checkbox locked: Adapter is running in read-only Observe mode.
                </p>
              )}
            </div>

            <div className="step-actions">
              <button
                type="button"
                className="promo-promote-btn"
                onClick={handlePromote}
                disabled={!confirmChecked || promoting || isObserveMode || isIdentical}
                style={{ whiteSpace: 'nowrap' }}
              >
                {promoting ? (
                  <>
                    <RefreshCw size={13} className="animate-spin" />
                    <span>Promoting…</span>
                  </>
                ) : (
                  <>
                    <Rocket size={13} />
                    <span>Promote</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* 6. Governance & Limitation Disclosure */}
      <div className="app-gap-notice" role="note">
        <Info size={14} style={{ flexShrink: 0 }} />
        <div>
          <strong>Audit and Rollback disclosure: </strong>
          Automatic one-click rollback and persistent promotion logs are not currently supported by backend database storage. Applied parameter values are stored directly in active adapter memory. To revert a promotion, manually re-apply the previous baseline values or restart the AutoTune engine.
        </div>
      </div>
    </div>
  );
}
