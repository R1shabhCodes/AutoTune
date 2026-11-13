import React from 'react';
import { 
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip 
} from 'recharts';
import { 
  Activity, Radio, SlidersHorizontal, Zap, Coins, 
  AlertCircle, CheckCircle2, Clock, Play, RefreshCw, Server
} from 'lucide-react';
import StatusBadge from '../common/StatusBadge';
import EmptyState from '../common/EmptyState';

export default function LiveMonitor({
  status = 'idle',
  wsStatus = 'connected',
  lastEventTime = null,
  activeExperimentId = null,
  trialBudget = 15,
  iterations = [],
  bestConfig = null,
  holdoutScore = null,
  errorMsg = null,
  onOpenWizard,
  activeAppName = 'Finance RAG (Internal)'
}) {
  const isRunning = status === 'running';

  // Filter iterations belonging to current active experiment if specified, or use recent iteration run
  const experimentIterations = activeExperimentId
    ? iterations.filter(it => it.experiment_id === activeExperimentId)
    : iterations.filter(it => it.experiment_id === iterations[0]?.experiment_id);

  // If no experiment_id match found, use latest iterations up to trialBudget
  const currentStudyTrials = experimentIterations.length > 0 
    ? experimentIterations 
    : iterations.slice(0, trialBudget);

  const completedCount = currentStudyTrials.length;
  const acceptedTrials = currentStudyTrials.filter(it => it.accepted === 1 || it.accepted === true);
  const acceptedCount = acceptedTrials.length;
  const rejectedCount = Math.max(0, completedCount - acceptedCount);
  const currentTrial = currentStudyTrials[0] || null;

  // Calculate study progress percentage
  const progressPercent = Math.min(100, Math.round((completedCount / Math.max(1, trialBudget)) * 100));

  // Trajectory chart data (chronological: oldest to newest)
  const chartData = [...currentStudyTrials]
    .filter(it => it.proposal_status !== 'failed_proposal' && typeof it.iteration_number === 'number')
    .sort((a, b) => a.iteration_number - b.iteration_number)
    .map(it => {
      const newScoreVal = typeof it.new_score === 'number' ? it.new_score : parseFloat(it.new_score) || 0;
      const compositeVal = typeof it.composite_score === 'number' ? it.composite_score : parseFloat(it.composite_score) || 0;
      const latencyVal = typeof it.avg_latency_ms === 'number' ? it.avg_latency_ms : parseFloat(it.avg_latency_ms) || 0;
      return {
        iteration: it.iteration_number,
        score: parseFloat(newScoreVal.toFixed(4)),
        composite: parseFloat(compositeVal.toFixed(4)),
        latency: latencyVal,
        accepted: it.accepted === 1 || it.accepted === true
      };
    });

  // Recharts custom tooltip
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="console-tooltip">
          <div className="console-tooltip-header">
            <span style={{ color: 'var(--color-muted)' }}>Trial</span>
            <span style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
              #{data.iteration}
            </span>
          </div>
          <div className="console-tooltip-row">
            <span style={{ color: 'var(--color-muted)' }}>Composite score</span>
            <span style={{ color: 'var(--color-cool)', fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
              {data.composite.toFixed(4)}
            </span>
          </div>
          <div className="console-tooltip-row">
            <span style={{ color: 'var(--color-muted)' }}>Tuning accuracy</span>
            <span style={{ color: 'var(--color-ink-muted)', fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
              {data.score.toFixed(4)}
            </span>
          </div>
          {data.latency > 0 && (
            <div className="console-tooltip-row">
              <span style={{ color: 'var(--color-muted)' }}>Average latency</span>
              <span style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                {data.latency.toFixed(0)}ms
              </span>
            </div>
          )}
          <div style={{ marginTop: 'var(--space-2xs)', borderTop: 'var(--rule-hair) solid var(--color-rule)', paddingTop: 'var(--space-2xs)' }}>
            <StatusBadge status={data.accepted ? 'accepted' : 'rejected'} label={data.accepted ? 'Accepted milestone' : 'Rejected candidate'} />
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="live-monitor-container">
      {/* 1. Live Telemetry Status Header */}
      <section className="console-panel monitor-header-panel" aria-label="Live monitor telemetry">
        <div className="monitor-header-left">
          <div className="monitor-status-indicator">
            <Radio 
              size={18} 
              className={isRunning ? 'monitor-radio-pulse is-running' : 'monitor-radio-pulse is-idle'} 
            />
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                <h1 className="monitor-heading">Live experiment monitor</h1>
                <StatusBadge 
                  status={isRunning ? 'running' : 'idle'} 
                  label={isRunning ? 'Study in progress' : completedCount > 0 ? 'Study complete' : 'Idle'} 
                />
              </div>
              <span className="monitor-subheading">
                Real-time WebSocket telemetry for Bayesian parameter trials and agent diagnostics.
              </span>
            </div>
          </div>
        </div>

        <div className="monitor-header-right">
          <div className="telemetry-pill-group">
            <div className="telemetry-chip">
              <Server size={12} style={{ color: 'var(--color-cool)' }} />
              <span className="chip-label">Target:</span>
              <span className="chip-val">{activeAppName}</span>
            </div>

            <div className="telemetry-chip">
              <span className={`ws-status-dot ${wsStatus}`} />
              <span className="chip-label">Telemetry stream:</span>
              <span className="chip-val" style={{ textTransform: 'capitalize' }}>{wsStatus}</span>
            </div>

            {lastEventTime && (
              <div className="telemetry-chip">
                <Clock size={12} style={{ color: 'var(--color-muted)' }} />
                <span className="chip-label">Last event:</span>
                <span className="chip-val mono-nums">{lastEventTime}</span>
              </div>
            )}
          </div>

          {onOpenWizard && (
            <button 
              type="button" 
              className="console-btn-wizard"
              onClick={onOpenWizard}
              disabled={isRunning}
              title="Configure and launch a new experiment"
            >
              <SlidersHorizontal size={13} />
              <span>Configure new run</span>
            </button>
          )}
        </div>
      </section>

      {/* Error Callout if any */}
      {errorMsg && (
        <div className="error-callout" role="alert">
          <AlertCircle size={15} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* 2. Study Execution Progress Banner */}
      <section className="console-panel monitor-progress-panel" aria-label="Active study progress">
        <div className="study-progress-top">
          <div className="study-id-box">
            <span className="study-meta-label">Experiment identifier</span>
            <span className="study-id-text mono-nums">
              {currentTrial?.experiment_id || activeExperimentId || 'Default study space'}
            </span>
          </div>

          <div className="study-counts-strip">
            <div className="study-count-item">
              <span className="count-label">Progress</span>
              <span className="count-val mono-nums">
                Trial {completedCount} <span className="count-total">/ {trialBudget}</span>
              </span>
            </div>

            <div className="study-count-item">
              <span className="count-label">Accepted milestones</span>
              <span className="count-val mono-nums" style={{ color: 'var(--color-sage)' }}>
                {acceptedCount}
              </span>
            </div>

            <div className="study-count-item">
              <span className="count-label">Rejected proposals</span>
              <span className="count-val mono-nums" style={{ color: 'var(--color-muted)' }}>
                {rejectedCount}
              </span>
            </div>

            <div className="study-count-item">
              <span className="count-label">Champion composite</span>
              <span className="count-val mono-nums highlight-cool">
                {bestConfig && typeof bestConfig.composite_score === 'number' 
                  ? bestConfig.composite_score.toFixed(4) 
                  : (currentTrial?.composite_score ? currentTrial.composite_score.toFixed(4) : '---')}
              </span>
            </div>
          </div>
        </div>

        {/* Hairline Progress Bar */}
        <div className="hairline-progress-wrapper" role="progressbar" aria-valuenow={progressPercent} aria-valuemin="0" aria-valuemax="100">
          <div 
            className={`hairline-progress-fill ${isRunning ? 'is-pulsing' : ''}`} 
            style={{ transform: `scaleX(${progressPercent / 100})` }} 
          />
        </div>
        <div className="progress-label-bar">
          <span className="progress-sub-text">
            {isRunning ? 'Sampling parameter bounds & computing evaluation metrics…' : completedCount > 0 ? 'Study evaluation cycle finished' : 'Ready to begin optimization'}
          </span>
          <span className="progress-percent-text mono-nums">{progressPercent}% complete</span>
        </div>
      </section>

      {/* 3. Live Metrics Row */}
      <div className="monitor-metrics-grid">
        <div className="console-panel metric-gauge-tile">
          <div className="gauge-header">
            <span className="gauge-title">Tuning accuracy</span>
            <CheckCircle2 size={15} style={{ color: 'var(--color-sage)' }} />
          </div>
          <div className="gauge-value-row">
            <span className="gauge-val mono-nums">
              {currentTrial?.new_score !== undefined ? currentTrial.new_score.toFixed(4) : '---'}
            </span>
            {currentTrial?.old_score !== undefined && currentTrial.old_score > 0 && (
              <span className="gauge-delta mono-nums">
                prev: {currentTrial.old_score.toFixed(3)}
              </span>
            )}
          </div>
          <span className="gauge-footer-note">Factual term containment pass rate</span>
        </div>

        <div className="console-panel metric-gauge-tile">
          <div className="gauge-header">
            <span className="gauge-title">Composite score</span>
            <Activity size={15} style={{ color: 'var(--color-cool)' }} />
          </div>
          <div className="gauge-value-row">
            <span className="gauge-val mono-nums" style={{ color: 'var(--color-cool)' }}>
              {currentTrial?.composite_score !== undefined ? currentTrial.composite_score.toFixed(4) : '---'}
            </span>
          </div>
          <span className="gauge-footer-note">Balanced accuracy & performance index</span>
        </div>

        <div className="console-panel metric-gauge-tile">
          <div className="gauge-header">
            <span className="gauge-title">Inference latency</span>
            <Zap size={15} style={{ color: 'var(--color-accent)' }} />
          </div>
          <div className="gauge-value-row">
            <span className="gauge-val mono-nums">
              {currentTrial?.avg_latency_ms ? `${currentTrial.avg_latency_ms.toFixed(0)}ms` : '---'}
            </span>
          </div>
          <span className="gauge-footer-note">Mean retrieval & generation time</span>
        </div>

        <div className="console-panel metric-gauge-tile">
          <div className="gauge-header">
            <span className="gauge-title">Token spend</span>
            <Coins size={15} style={{ color: 'var(--color-muted)' }} />
          </div>
          <div className="gauge-value-row">
            <span className="gauge-val mono-nums">
              {currentTrial?.total_tokens ? currentTrial.total_tokens.toLocaleString() : '---'}
            </span>
          </div>
          <span className="gauge-footer-note">Cumulative context and prompt tokens</span>
        </div>
      </div>

      {/* 4. Split Grid: Live Trajectory Graph + Real-time Diagnostic Event Feed */}
      <div className="monitor-split-grid">
        {/* Trajectory Graph */}
        <section className="console-panel monitor-chart-panel" aria-label="Live parameter trajectory">
          <div className="panel-header">
            <div className="panel-title-group">
              <h2 className="panel-title">Real-time study trajectory</h2>
            </div>
            <div className="legend-strip">
              <span className="legend-item">
                <span className="legend-line solid-cool" /> Composite score
              </span>
              <span className="legend-item">
                <span className="legend-line dashed-muted" /> Accuracy
              </span>
              <span className="legend-item">
                <span className="legend-dot sage" /> Accepted milestone
              </span>
            </div>
          </div>

          <div className="panel-body">
            {chartData.length > 0 ? (
              <div className="chart-container" style={{ width: '100%', height: '320px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 12, right: 16, left: -16, bottom: 0 }}>
                    <CartesianGrid stroke="var(--color-rule)" strokeDasharray="" />
                    <XAxis 
                      dataKey="iteration" 
                      stroke="var(--color-ink-muted)" 
                      tickLine={false}
                      tick={{ fill: 'var(--color-ink-muted)', fontSize: 11, fontFamily: 'var(--font-outlier)' }}
                    />
                    <YAxis 
                      stroke="var(--color-ink-muted)" 
                      domain={[0.0, 1.0]} 
                      tickLine={false}
                      tick={{ fill: 'var(--color-ink-muted)', fontSize: 11, fontFamily: 'var(--font-outlier)' }}
                      tickFormatter={(val) => val.toFixed(2)}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    {/* Accuracy reference line */}
                    <Line 
                      type="monotone" 
                      dataKey="score" 
                      stroke="var(--color-cool-soft)" 
                      strokeWidth={1.5}
                      strokeDasharray="3 3"
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 0, fill: 'var(--color-cool-soft)' }}
                    />
                    {/* Primary Composite score curve */}
                    <Line 
                      type="monotone" 
                      dataKey="composite" 
                      stroke="var(--color-cool)" 
                      strokeWidth={2}
                      dot={(props) => {
                        const { cx, cy, payload } = props;
                        if (!payload || payload.iteration === 0) return null;
                        if (!payload.accepted) return null;
                        return (
                          <circle 
                            key={`${payload.iteration}-milestone-dot`}
                            cx={cx} 
                            cy={cy} 
                            r={4} 
                            fill="var(--color-sage)" 
                            stroke="var(--color-paper-1)"
                            strokeWidth={1.5}
                          />
                        );
                      }}
                      activeDot={{ r: 5.5, strokeWidth: 1.5, stroke: 'var(--color-paper-1)', fill: 'var(--color-cool)' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="empty-panel-body">
                <EmptyState 
                  title="Awaiting live telemetry" 
                  description="Start an optimization run using the wizard above to visualize the real-time parameter score progression curve." 
                />
              </div>
            )}
          </div>
        </section>

        {/* Live Diagnostic Audit Feed */}
        <section className="console-panel monitor-feed-panel" aria-label="Real-time trial diagnostics">
          <div className="panel-header">
            <div className="panel-title-group">
              <h2 className="panel-title">Live trial events</h2>
              <span className="item-count-badge mono-nums">
                {currentStudyTrials.length} {currentStudyTrials.length === 1 ? 'event' : 'events'}
              </span>
            </div>
            {isRunning && (
              <span className="streaming-badge">
                <RefreshCw className="animate-spin" size={11} /> Streaming live
              </span>
            )}
          </div>

          <div className="feed-scroll-container">
            {currentStudyTrials.length > 0 ? (
              currentStudyTrials.map((item) => {
                const isBaseline = item.param === '[Baseline]' || item.proposal_status === 'baseline';
                return (
                  <article 
                    key={item.iteration_number} 
                    className={`diagnostic-card ${item.accepted ? 'is-accepted' : 'is-rejected'}`}
                  >
                    <div className="diagnostic-header">
                      <div className="diagnostic-title-group">
                        <span className="diagnostic-iter-num mono-nums">
                          Trial #{item.iteration_number}
                        </span>
                        <StatusBadge 
                          status={isBaseline ? 'baseline' : item.accepted ? 'accepted' : 'rejected'} 
                          label={isBaseline ? 'Baseline' : item.accepted ? 'Accepted' : 'Rejected'} 
                        />
                        {typeof item.avg_latency_ms === 'number' && item.avg_latency_ms > 0 && (
                          <span className="diagnostic-telemetry-tag">
                            <Zap size={11} />
                            <span>{item.avg_latency_ms.toFixed(0)}ms</span>
                          </span>
                        )}
                      </div>
                      <span className="diagnostic-timestamp mono-nums">{item.timestamp}</span>
                    </div>

                    {item.hypothesis && !isBaseline && (
                      <blockquote className="diagnostic-hypothesis">
                        “{item.hypothesis}”
                      </blockquote>
                    )}

                    <div className="diagnostic-diff-row">
                      <div className="diff-param-box">
                        {isBaseline ? (
                          <span style={{ color: 'var(--color-cool)', fontWeight: 500 }}>
                            Baseline configuration initialized
                          </span>
                        ) : (
                          <div className="diff-pair">
                            <span className="diff-param-name">{item.param}</span>:
                            <span className="diff-val-old">{item.old_value}</span>
                            <span className="diff-arrow">→</span>
                            <span className="diff-val-new">{item.new_value}</span>
                          </div>
                        )}
                      </div>

                      <div className="diff-scores-box">
                        <div className="diff-score-item">
                          <span className="diff-score-label">Comp:</span>
                          <span className="diff-score-num highlight mono-nums">
                            {typeof item.composite_score === 'number' ? item.composite_score.toFixed(4) : (item.new_score ? item.new_score.toFixed(4) : '---')}
                          </span>
                        </div>
                      </div>
                    </div>

                    {item.rejection_reason && (
                      <div className="diagnostic-rejection-notice">
                        Reason: {item.rejection_reason}
                      </div>
                    )}
                  </article>
                );
              })
            ) : (
              <div className="empty-panel-body">
                <EmptyState 
                  title="No live events captured" 
                  description="When an optimization experiment starts, trials stream live into this audit log." 
                />
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
