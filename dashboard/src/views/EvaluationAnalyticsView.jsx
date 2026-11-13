import React, { useState, useMemo } from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip
} from 'recharts';
import {
  CheckCircle2, Sparkles, ShieldCheck, Download,
  Clock, Zap, Coins, Sliders, ArrowUpRight, Info,
  Filter, FileText, Activity
} from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import EmptyState from '../components/common/EmptyState';
import TrialDetailDrawer from '../components/history/TrialDetailDrawer';

export default function EvaluationAnalyticsView({
  iterations = [],
  holdoutScore = null,
  bestConfig = null,
  onDownloadReport = null
}) {
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'accepted' | 'rejected' | 'baseline'
  const [selectedTrial, setSelectedTrial] = useState(null);

  // Filter valid iterations
  const validIterations = useMemo(() => {
    return [...iterations].filter(it => typeof it.iteration_number === 'number');
  }, [iterations]);

  // Aggregate telemetry calculation
  const stats = useMemo(() => {
    const total = validIterations.length;
    const accepted = validIterations.filter(it => it.accepted === 1 || it.accepted === true).length;
    const rejected = total - accepted;

    const latencies = validIterations
      .map(it => it.avg_latency_ms)
      .filter(l => typeof l === 'number' && l > 0);
    const avgLatency = latencies.length > 0
      ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
      : 0;

    const totalTokens = validIterations
      .map(it => it.total_tokens)
      .filter(t => typeof t === 'number' && t > 0)
      .reduce((a, b) => a + b, 0);

    const scores = validIterations
      .map(it => typeof it.new_score === 'number' ? it.new_score : parseFloat(it.new_score) || 0)
      .filter(s => s > 0);
    const avgScore = scores.length > 0
      ? (scores.reduce((a, b) => a + b, 0) / scores.length)
      : 0;

    const bestScore = bestConfig?.score || (scores.length > 0 ? Math.max(...scores) : 0);

    return { total, accepted, rejected, avgLatency, totalTokens, avgScore, bestScore };
  }, [validIterations, bestConfig]);

  // Filtered table rows
  const filteredRows = useMemo(() => {
    let rows = [...validIterations].sort((a, b) => b.iteration_number - a.iteration_number);
    if (statusFilter === 'accepted') {
      rows = rows.filter(it => it.accepted === 1 || it.accepted === true);
    } else if (statusFilter === 'rejected') {
      rows = rows.filter(it => (it.accepted === 0 || it.accepted === false) && it.param !== '[Baseline]' && it.iteration_number !== 0);
    } else if (statusFilter === 'baseline') {
      rows = rows.filter(it => it.param === '[Baseline]' || it.iteration_number === 0 || it.proposal_status === 'baseline');
    }
    return rows;
  }, [validIterations, statusFilter]);

  // Chart data
  const chartData = useMemo(() => {
    return [...validIterations]
      .filter(it => it.proposal_status !== 'failed_proposal')
      .sort((a, b) => a.iteration_number - b.iteration_number)
      .map(it => {
        const scoreVal = typeof it.new_score === 'number' ? it.new_score : parseFloat(it.new_score) || 0;
        const compVal = typeof it.composite_score === 'number' ? it.composite_score : parseFloat(it.composite_score) || scoreVal;
        return {
          iteration: it.iteration_number,
          score: parseFloat(scoreVal.toFixed(4)),
          composite: parseFloat(compVal.toFixed(4)),
          latency: it.avg_latency_ms || 0,
          accepted: it.accepted === 1 || it.accepted === true
        };
      });
  }, [validIterations]);

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
    <div className="eval-analytics-root">
      {/* 1. Header */}
      <div className="page-header-block">
        <div className="page-title-group">
          <div className="page-title-row">
            <CheckCircle2 size={18} style={{ color: 'var(--color-cool)' }} />
            <h1 className="page-title">Evaluation analytics and benchmarks</h1>
          </div>
          <p className="page-subtitle">
            Historical evaluation performance, deterministic term pass rates, holdout anti-overfitting benchmarks, and execution timing metrics.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
          <button
            type="button"
            className="console-btn-wizard text-nowrap"
            onClick={onDownloadReport || (() => { window.location.href = '/report/current'; })}
            disabled={validIterations.length === 0}
            title="Download full Markdown evaluation report"
          >
            <Download size={13} />
            <span>Download report</span>
          </button>
        </div>
      </div>

      {/* 2. Primary KPI Stat Tiles */}
      <div className="eval-kpi-grid">
        <section className="console-panel eval-kpi-tile" aria-label="Tuning accuracy metric">
          <span className="eval-kpi-label">Peak tuning accuracy</span>
          <div className="eval-kpi-main">
            <span className="eval-kpi-val mono-nums" style={{ color: 'var(--color-sage)' }}>
              {(stats.bestScore * 100).toFixed(1)}%
            </span>
            <span className="eval-kpi-sub">
              Mean study: {(stats.avgScore * 100).toFixed(1)}%
            </span>
          </div>
        </section>

        <section className="console-panel eval-kpi-tile" aria-label="Holdout qualification metric">
          <span className="eval-kpi-label">Holdout benchmark score</span>
          <div className="eval-kpi-main">
            <span className="eval-kpi-val mono-nums" style={{ color: 'var(--color-cool)' }}>
              {holdoutScore !== null ? holdoutScore.toFixed(4) : '---'}
            </span>
            <span className="eval-kpi-sub">
              Protected blind holdout partition
            </span>
          </div>
        </section>

        <section className="console-panel eval-kpi-tile" aria-label="Inference latency metric">
          <span className="eval-kpi-label">Mean roundtrip latency</span>
          <div className="eval-kpi-main">
            <span className="eval-kpi-val mono-nums">
              {stats.avgLatency > 0 ? `${stats.avgLatency}ms` : '---'}
            </span>
            <span className="eval-kpi-sub">
              Retrieval and LLM generation
            </span>
          </div>
        </section>

        <section className="console-panel eval-kpi-tile" aria-label="Token budget metric">
          <span className="eval-kpi-label">Total token spend</span>
          <div className="eval-kpi-main">
            <span className="eval-kpi-val mono-nums">
              {stats.totalTokens > 0 ? stats.totalTokens.toLocaleString() : '---'}
            </span>
            <span className="eval-kpi-sub">
              Accumulated across {stats.total} trials
            </span>
          </div>
        </section>
      </div>

      {/* 3. Performance Trend Progression Chart */}
      <section className="console-panel eval-chart-panel" aria-label="Evaluation performance chart">
        <div className="panel-header">
          <div className="panel-title-group">
            <Activity size={16} style={{ color: 'var(--color-cool)' }} />
            <h2 className="panel-title">Multi-objective evaluation trajectory</h2>
          </div>
          <div className="chart-legend-strip">
            <span className="legend-chip">
              <span className="legend-line cool-solid" /> Composite score
            </span>
            <span className="legend-chip">
              <span className="legend-line cool-dashed" /> Accuracy
            </span>
            <span className="legend-chip">
              <span className="legend-dot sage" /> Milestone
            </span>
          </div>
        </div>

        <div className="panel-body">
          {chartData.length > 0 ? (
            <div style={{ width: '100%', height: '300px' }}>
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
                  <Line
                    type="monotone"
                    dataKey="score"
                    name="Accuracy"
                    stroke="var(--color-cool-soft)"
                    strokeWidth={1.5}
                    strokeDasharray="3 3"
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="composite"
                    name="Composite score"
                    stroke="var(--color-cool)"
                    strokeWidth={2}
                    dot={(props) => {
                      const { cx, cy, payload } = props;
                      if (!payload || payload.iteration === 0) return null;
                      if (!payload.accepted) return null;
                      return (
                        <circle
                          key={`${payload.iteration}-dot`}
                          cx={cx}
                          cy={cy}
                          r={4}
                          fill="var(--color-sage)"
                          stroke="var(--color-paper-1)"
                          strokeWidth={1.5}
                        />
                      );
                    }}
                    activeDot={{ r: 5, strokeWidth: 1.5, stroke: 'var(--color-paper-1)', fill: 'var(--color-cool)' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-panel-body">
              <EmptyState
                title="No evaluation history captured"
                description="Run optimization trials to generate multi-objective trajectory graphs."
              />
            </div>
          )}
        </div>
      </section>

      {/* 4. Evaluated Trials Table & Inspection */}
      <div className={`eval-table-split ${selectedTrial ? 'has-drawer' : ''}`}>
        <section className="console-panel eval-table-panel" aria-label="Evaluated trials table">
          <div className="panel-header">
            <div className="panel-title-group">
              <Filter size={15} style={{ color: 'var(--color-muted)' }} />
              <h2 className="panel-title">Evaluation records</h2>
              <span className="item-count-badge mono-nums">{filteredRows.length} trials</span>
            </div>

            <div className="diff-filter-tabs" role="tablist" aria-label="Status filters">
              <button
                type="button"
                role="tab"
                aria-selected={statusFilter === 'all'}
                className={`diff-tab-btn ${statusFilter === 'all' ? 'is-active' : ''}`}
                onClick={() => setStatusFilter('all')}
              >
                <span>All</span>
                <span className="diff-count-pill mono-nums">{validIterations.length}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={statusFilter === 'accepted'}
                className={`diff-tab-btn ${statusFilter === 'accepted' ? 'is-active' : ''}`}
                onClick={() => setStatusFilter('accepted')}
              >
                <span>Accepted</span>
                <span className="diff-count-pill mono-nums">{stats.accepted}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={statusFilter === 'rejected'}
                className={`diff-tab-btn ${statusFilter === 'rejected' ? 'is-active' : ''}`}
                onClick={() => setStatusFilter('rejected')}
              >
                <span>Rejected</span>
                <span className="diff-count-pill mono-nums">{stats.rejected}</span>
              </button>
            </div>
          </div>

          <div className="table-scroll-container">
            <table className="console-table" aria-label="Evaluation details table">
              <thead>
                <tr>
                  <th style={{ width: '60px' }}>Trial</th>
                  <th>Parameter proposal</th>
                  <th>Accuracy</th>
                  <th>Latency</th>
                  <th>Tokens</th>
                  <th>Composite</th>
                  <th style={{ width: '90px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map(item => {
                  const isSelected = selectedTrial?.iteration_number === item.iteration_number;
                  const isBaseline = item.param === '[Baseline]' || item.param === 'None' || item.iteration_number === 0 || item.proposal_status === 'baseline';
                  const newComp = typeof item.composite_score === 'number'
                    ? item.composite_score
                    : (typeof item.new_score === 'number' ? item.new_score : 0);

                  return (
                    <tr
                      key={item.iteration_number}
                      className={`eval-tr-clickable ${isSelected ? 'row-selected' : ''}`}
                      onClick={() => setSelectedTrial(prev => prev?.iteration_number === item.iteration_number ? null : item)}
                      tabIndex={0}
                      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && setSelectedTrial(item)}
                    >
                      <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                        #{item.iteration_number}
                      </td>
                      <td>
                        {isBaseline ? (
                          <span style={{ color: 'var(--color-muted)' }}>Baseline</span>
                        ) : (
                          <span className="param-name-tag">{item.param}</span>
                        )}
                      </td>
                      <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                        {typeof item.new_score === 'number' ? item.new_score.toFixed(4) : parseFloat(item.new_score || 0).toFixed(4)}
                      </td>
                      <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                        {item.avg_latency_ms > 0 ? `${item.avg_latency_ms.toFixed(0)}ms` : '---'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                        {item.total_tokens > 0 ? item.total_tokens.toLocaleString() : '---'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
                        {newComp.toFixed(4)}
                      </td>
                      <td>
                        <StatusBadge
                          status={isBaseline ? 'baseline' : item.accepted ? 'accepted' : 'rejected'}
                          label={isBaseline ? 'Baseline' : item.accepted ? 'Accepted' : 'Rejected'}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Selected Trial Detail Drawer */}
        {selectedTrial && (
          <TrialDetailDrawer
            trial={selectedTrial}
            onClose={() => setSelectedTrial(null)}
          />
        )}
      </div>

      {/* 5. Metrics Framework Overview Note */}
      <div className="app-gap-notice" role="note">
        <Info size={14} style={{ flexShrink: 0 }} />
        <div>
          <strong>Evaluation Engine 2.0 Telemetry Framework: </strong>
          Evaluations compute exact string normalization match, deterministic expected term pass rates, and anti-overfitting holdout benchmarks. Individual question telemetry is persisted for modern evaluation cycles. Click any trial record in the table above to inspect parameter deltas and diagnostic rationale.
        </div>
      </div>
    </div>
  );
}

