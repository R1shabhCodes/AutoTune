import React, { useState, useEffect } from 'react';
import {
  X, Activity, Sliders, Zap, Coins, CheckCircle2,
  XCircle, AlertCircle, FileText, Code2, Clock,
  ListFilter, ShieldAlert, ChevronRight, HelpCircle
} from 'lucide-react';
import StatusBadge from '../common/StatusBadge';
import { api } from '../../api/client';

export default function TrialDetailDrawer({
  trial = null,
  onClose = () => { }
}) {
  const [questionEvals, setQuestionEvals] = useState([]);
  const [loadingEvals, setLoadingEvals] = useState(false);
  const [evalTab, setEvalTab] = useState('overview'); // 'overview' | 'snapshot' | 'questions'

  useEffect(() => {
    if (!trial) return;
    const trialId = trial.trial_id || `trial_${trial.experiment_id || 'legacy'}_${trial.iteration_number}`;
    setLoadingEvals(true);
    api.getTrialEvaluations(trialId)
      .then(res => {
        setQuestionEvals(Array.isArray(res) ? res : []);
      })
      .catch(err => {
        console.warn('Could not load question evaluations for trial:', err);
        setQuestionEvals([]);
      })
      .finally(() => {
        setLoadingEvals(false);
      });
  }, [trial]);

  if (!trial) return null;

  // Parse configuration snapshot if available
  let configSnapshot = null;
  if (trial.config_snapshot) {
    try {
      configSnapshot = typeof trial.config_snapshot === 'string'
        ? JSON.parse(trial.config_snapshot)
        : trial.config_snapshot;
    } catch (_) {
      configSnapshot = null;
    }
  }

  const isBaseline = trial.param === '[Baseline]' || trial.param === 'None' || trial.iteration_number === 0 || trial.proposal_status === 'baseline';
  const isFailedProposal = trial.proposal_status === 'failed_proposal' || trial.param === '[Unavailable]';
  const isInvalidProposal = trial.proposal_status === 'invalid_proposal';

  const newAcc = typeof trial.new_score === 'number' ? trial.new_score : parseFloat(trial.new_score) || 0;
  const oldAcc = typeof trial.old_score === 'number' ? trial.old_score : parseFloat(trial.old_score) || 0;
  const composite = typeof trial.composite_score === 'number'
    ? trial.composite_score
    : (trial.composite_score !== undefined && trial.composite_score !== null ? parseFloat(trial.composite_score) : newAcc);

  return (
    <aside className="app-drawer trial-drawer" aria-label="Trial details" role="complementary">
      {/* Drawer Header */}
      <div className="app-drawer-header">
        <div className="app-drawer-title-group">
          <Activity size={16} style={{ color: 'var(--color-cool)' }} />
          <span className="app-drawer-title mono-nums">
            Trial #{trial.iteration_number}
          </span>
          <StatusBadge
            status={isBaseline ? 'baseline' : trial.accepted ? 'accepted' : 'rejected'}
            label={isBaseline ? 'Baseline' : trial.accepted ? 'Accepted' : 'Rejected'}
          />
        </div>
        <button
          type="button"
          className="app-drawer-close"
          onClick={onClose}
          aria-label="Close trial details"
        >
          <X size={15} />
        </button>
      </div>

      {/* Tabs */}
      <div className="trial-drawer-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={evalTab === 'overview'}
          className={`trial-tab-btn ${evalTab === 'overview' ? 'is-active' : ''}`}
          onClick={() => setEvalTab('overview')}
        >
          Overview
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={evalTab === 'snapshot'}
          className={`trial-tab-btn ${evalTab === 'snapshot' ? 'is-active' : ''}`}
          onClick={() => setEvalTab('snapshot')}
        >
          Configuration snapshot
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={evalTab === 'questions'}
          className={`trial-tab-btn ${evalTab === 'questions' ? 'is-active' : ''}`}
          onClick={() => setEvalTab('questions')}
        >
          Sample evaluations ({questionEvals.length})
        </button>
      </div>

      <div className="app-drawer-scroll">
        {evalTab === 'overview' && (
          <>
            {/* Metadata Summary */}
            <section className="app-drawer-section">
              <h3 className="app-drawer-section-title">Execution metadata</h3>
              <div className="app-detail-grid">
                <div className="app-detail-row">
                  <span className="app-detail-label">Study ID</span>
                  <span className="app-detail-value mono-nums">{trial.experiment_id || 'exp_legacy'}</span>
                </div>
                <div className="app-detail-row">
                  <span className="app-detail-label">Trial ID</span>
                  <span className="app-detail-value mono-nums">{trial.trial_id || `trial_${trial.iteration_number}`}</span>
                </div>
                <div className="app-detail-row">
                  <span className="app-detail-label">Timestamp</span>
                  <span className="app-detail-value mono-nums">{trial.timestamp}</span>
                </div>
                <div className="app-detail-row">
                  <span className="app-detail-label">Proposal status</span>
                  <span className="app-detail-value mono-nums">{trial.proposal_status || 'success'}</span>
                </div>
              </div>
            </section>

            {/* Parameter Change */}
            <section className="app-drawer-section">
              <h3 className="app-drawer-section-title">Parameter modification</h3>
              <div className="trial-param-box">
                {isBaseline ? (
                  <span style={{ color: 'var(--color-cool)', fontWeight: 500 }}>
                    Initial baseline state
                  </span>
                ) : isFailedProposal ? (
                  <span style={{ color: 'var(--color-bad)' }}>
                    Proposal generation failed (LLM offline or invalid format)
                  </span>
                ) : (
                  <div className="diff-pair">
                    <span className="diff-param-name">{trial.param}</span>:
                    <span className="diff-val-old mono-nums">{String(trial.old_value)}</span>
                    <span className="diff-arrow">→</span>
                    <span className="diff-val-new mono-nums">{String(trial.new_value)}</span>
                  </div>
                )}
              </div>
            </section>

            {/* Score & Telemetry Cards */}
            <section className="app-drawer-section">
              <h3 className="app-drawer-section-title">Evaluation telemetry</h3>
              <div className="trial-metrics-grid">
                <div className="trial-metric-tile">
                  <span className="trial-metric-lbl">Tuning accuracy</span>
                  <span className="trial-metric-val mono-nums" style={{ color: trial.accepted ? 'var(--color-sage)' : 'var(--color-ink)' }}>
                    {newAcc.toFixed(4)}
                  </span>
                  {!isBaseline && oldAcc > 0 && (
                    <span className="trial-metric-delta mono-nums">
                      Prev: {oldAcc.toFixed(4)}
                    </span>
                  )}
                </div>

                <div className="trial-metric-tile">
                  <span className="trial-metric-lbl">Composite score</span>
                  <span className="trial-metric-val mono-nums" style={{ color: 'var(--color-cool)' }}>
                    {composite.toFixed(4)}
                  </span>
                </div>

                <div className="trial-metric-tile">
                  <span className="trial-metric-lbl">Mean latency</span>
                  <span className="trial-metric-val mono-nums">
                    {trial.avg_latency_ms > 0 ? `${trial.avg_latency_ms.toFixed(0)}ms` : '---'}
                  </span>
                </div>

                <div className="trial-metric-tile">
                  <span className="trial-metric-lbl">Token spend</span>
                  <span className="trial-metric-val mono-nums">
                    {trial.total_tokens > 0 ? trial.total_tokens.toLocaleString() : '---'}
                  </span>
                </div>
              </div>
            </section>

            {/* Agent Hypothesis */}
            {trial.hypothesis && !isBaseline && (
              <section className="app-drawer-section">
                <h3 className="app-drawer-section-title">Diagnostic hypothesis</h3>
                <blockquote className="diagnostic-hypothesis" style={{ margin: 0 }}>
                  “{trial.hypothesis}”
                </blockquote>
                {trial.motivated_by && (
                  <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--color-muted)', marginTop: 'var(--space-2xs)' }}>
                    Targeting failure: {trial.motivated_by}
                  </span>
                )}
              </section>
            )}

            {/* Rejection / Failure Notice */}
            {trial.rejection_reason && (
              <section className="app-drawer-section">
                <h3 className="app-drawer-section-title" style={{ color: 'var(--color-bad)' }}>
                  Rejection explanation
                </h3>
                <div className="diagnostic-rejection-notice" style={{ margin: 0 }}>
                  {trial.rejection_reason}
                </div>
              </section>
            )}
          </>
        )}

        {/* Tab 2: Snapshot */}
        {evalTab === 'snapshot' && (
          <section className="app-drawer-section">
            <h3 className="app-drawer-section-title">Immutable configuration snapshot</h3>
            {configSnapshot ? (
              <div className="app-config-snapshot">
                {Object.entries(configSnapshot).map(([k, v]) => (
                  <div key={k} className="app-config-row">
                    <span className="app-config-key mono-nums">{k}</span>
                    <span className="app-config-val mono-nums">{String(v)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="app-gap-notice" role="note">
                <Info size={14} style={{ flexShrink: 0 }} />
                <span>
                  No explicit JSON snapshot was persisted for this legacy trial. Reconstructed parameters are visible in the differential comparison view.
                </span>
              </div>
            )}
          </section>
        )}

        {/* Tab 3: Sample Questions */}
        {evalTab === 'questions' && (
          <section className="app-drawer-section">
            <h3 className="app-drawer-section-title">Per-question evaluation breakdown</h3>
            {loadingEvals ? (
              <div className="app-loading-state">
                <span>Loading granular evaluation telemetry…</span>
              </div>
            ) : questionEvals.length > 0 ? (
              <div className="question-eval-list">
                {questionEvals.map((q, idx) => (
                  <div key={q.id || idx} className="question-eval-card">
                    <div className="question-eval-header">
                      <span className="question-num mono-nums">Sample #{idx + 1}</span>
                      <StatusBadge
                        status={q.expected_term_pass_rate >= 1.0 ? 'healthy' : 'rejected'}
                        label={q.expected_term_pass_rate >= 1.0 ? 'Passed' : 'Degraded'}
                      />
                    </div>
                    <div className="question-text">
                      <strong>Q: </strong>{q.question}
                    </div>
                    {q.generated_answer && (
                      <div className="question-answer">
                        <strong>Generated: </strong>{q.generated_answer}
                      </div>
                    )}
                    <div className="question-telemetry-strip">
                      <span className="q-tag mono-nums">Pass rate: {((q.expected_term_pass_rate || 0) * 100).toFixed(0)}%</span>
                      {q.latency_ms > 0 && (
                        <span className="q-tag mono-nums">{q.latency_ms.toFixed(0)}ms</span>
                      )}
                      {q.numerical_grounding_passed !== null && (
                        <span className={`q-tag ${q.numerical_grounding_passed ? 'pass' : 'fail'}`}>
                          {q.numerical_grounding_passed ? 'Grounded' : 'Ungrounded numbers'}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="app-gap-notice" role="note">
                <Info size={14} style={{ flexShrink: 0 }} />
                <span>
                  Per-question sample breakdown was not recorded for this historical trial. The database persisted aggregate study telemetry for this run.
                </span>
              </div>
            )}
          </section>
        )}
      </div>
    </aside>
  );
}
