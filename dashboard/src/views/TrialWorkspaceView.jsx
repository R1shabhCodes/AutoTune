import React, { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import {
  Play, Activity, Sliders, RefreshCw, Download,
  GitCompare, Zap, Coins, FileText, X, AlertCircle, SlidersHorizontal,
  Search, Filter, ChevronLeft, ChevronRight, Eye, Layers
} from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import EmptyState from '../components/common/EmptyState';
import ExperimentWizard from '../components/experiment/ExperimentWizard';
import TrialDetailDrawer from '../components/history/TrialDetailDrawer';
import { api } from '../api/client';

export default function TrialWorkspaceView({
  iterations = [],
  bestConfig = null,
  holdoutScore = null,
  status = 'idle',
  runCount = 15,
  setRunCount,
  onStartRun,
  errorMsg = null,
  onDownloadReport,
  adapters = []
}) {
  const [viewMode, setViewMode] = useState('chart'); // 'chart' | 'table'
  const [selectedIters, setSelectedIters] = useState([]);
  const [showCompareModal, setShowCompareModal] = useState(false);
  const [isWizardOpen, setIsWizardOpen] = useState(false);

  // Phase 5 Trial Inspection & History State
  const [selectedTrial, setSelectedTrial] = useState(null);
  const [experimentsList, setExperimentsList] = useState([]);
  const [selectedExperimentId, setSelectedExperimentId] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'accepted' | 'rejected' | 'baseline'
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 12;

  useEffect(() => {
    api.getExperiments()
      .then(res => setExperimentsList(Array.isArray(res) ? res : []))
      .catch(() => setExperimentsList([]));
  }, []);

  // Filtered table rows with pagination
  const filteredTableRows = useMemo(() => {
    let rows = [...iterations];
    if (selectedExperimentId !== 'all') {
      rows = rows.filter(it => it.experiment_id === selectedExperimentId);
    }
    if (statusFilter === 'accepted') {
      rows = rows.filter(it => it.accepted === 1 || it.accepted === true);
    } else if (statusFilter === 'rejected') {
      rows = rows.filter(it => (it.accepted === 0 || it.accepted === false) && it.param !== '[Baseline]' && it.iteration_number !== 0);
    } else if (statusFilter === 'baseline') {
      rows = rows.filter(it => it.param === '[Baseline]' || it.iteration_number === 0 || it.proposal_status === 'baseline');
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      rows = rows.filter(it =>
        (it.param && it.param.toLowerCase().includes(q)) ||
        (it.hypothesis && it.hypothesis.toLowerCase().includes(q)) ||
        (it.experiment_id && it.experiment_id.toLowerCase().includes(q))
      );
    }
    return rows.sort((a, b) => b.iteration_number - a.iteration_number);
  }, [iterations, selectedExperimentId, statusFilter, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(filteredTableRows.length / pageSize));
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredTableRows.slice(start, start + pageSize);
  }, [filteredTableRows, currentPage, pageSize]);

  // Close modal on ESC key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && showCompareModal) {
        setShowCompareModal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showCompareModal]);

  // Process data for Recharts (oldest to newest)
  const chartData = [...iterations]
    .filter(it => it.proposal_status !== 'failed_proposal' && typeof it.iteration_number === 'number')
    .sort((a, b) => a.iteration_number - b.iteration_number)
    .map((item) => {
      const newScoreVal = typeof item.new_score === 'number' ? item.new_score : parseFloat(item.new_score) || 0;
      const compositeVal = typeof item.composite_score === 'number' ? item.composite_score : parseFloat(item.composite_score) || 0;
      const latencyVal = typeof item.avg_latency_ms === 'number' ? item.avg_latency_ms : parseFloat(item.avg_latency_ms) || 0;
      return {
        iteration: item.iteration_number,
        score: parseFloat(newScoreVal.toFixed(4)),
        composite: parseFloat(compositeVal.toFixed(4)),
        latency: latencyVal,
        param: item.param,
        accepted: item.accepted === 1 || item.accepted === true
      };
    });

  // Recharts Custom Tooltip (Console style)
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="console-tooltip">
          <div className="console-tooltip-header">
            <span style={{ color: 'var(--color-muted)' }}>Iteration</span>
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
          {data.param && data.param !== 'None' && data.param !== '[Baseline]' && (
            <div className="console-tooltip-row">
              <span style={{ color: 'var(--color-muted)' }}>Parameter</span>
              <span style={{ color: 'var(--color-cool)', fontFamily: 'var(--font-outlier)' }}>
                {data.param}
              </span>
            </div>
          )}
          <div style={{ marginTop: 'var(--space-2xs)', borderTop: 'var(--rule-hair) solid var(--color-rule)', paddingTop: 'var(--space-2xs)' }}>
            <StatusBadge status={data.accepted ? 'accepted' : 'rejected'} label={data.accepted ? 'Accepted milestone' : 'Rejected'} />
          </div>
        </div>
      );
    }
    return null;
  };

  // Selection logic for comparison (max 2)
  const handleToggleSelect = (iterNum) => {
    setSelectedIters((prev) => {
      if (prev.includes(iterNum)) {
        return prev.filter((id) => id !== iterNum);
      }
      if (prev.length >= 2) {
        return prev;
      }
      return [...prev, iterNum];
    });
  };

  const isCheckboxDisabled = (iterNum) => {
    return !selectedIters.includes(iterNum) && selectedIters.length >= 2;
  };

  // Reconstruct config for comparison
  const getConfigAtIteration = (iterNum) => {
    if (!bestConfig || !bestConfig.config) return null;
    const config = { ...bestConfig.config };
    const sortedIters = [...iterations].sort((a, b) => b.iteration_number - a.iteration_number);
    for (const item of sortedIters) {
      if (item.iteration_number > iterNum && item.accepted && item.param !== 'None') {
        const paramKey = item.param;
        const currentVal = config[paramKey];
        let oldVal = item.old_value;
        if (typeof currentVal === 'number') {
          oldVal = Number(oldVal);
        }
        config[paramKey] = oldVal;
      }
    }
    return config;
  };

  const sortedSelected = [...selectedIters].sort((a, b) => a - b);
  const iterA = iterations.find(it => it.iteration_number === sortedSelected[0]);
  const iterB = iterations.find(it => it.iteration_number === sortedSelected[1]);
  const configA = iterA ? getConfigAtIteration(iterA.iteration_number) : null;
  const configB = iterB ? getConfigAtIteration(iterB.iteration_number) : null;

  const renderConfigCompareRow = (label, key) => {
    const valA = configA ? configA[key] : 'N/A';
    const valB = configB ? configB[key] : 'N/A';
    const isDifferent = valA !== valB;
    return (
      <tr key={key} className={isDifferent ? 'diff-row-changed' : ''}>
        <td className="param-label-cell">{label}</td>
        <td className={`param-value-cell ${isDifferent ? 'value-changed-a' : ''}`}>
          {String(valA)}
        </td>
        <td className={`param-value-cell ${isDifferent ? 'value-changed-b' : ''}`}>
          {String(valB)}
        </td>
      </tr>
    );
  };

  const isRunning = status === 'running';

  return (
    <div className="workspace-container">
      {/* Top Grid: Controls + Champion Configuration */}
      <div className="workspace-top-grid">
        {/* Controls Card */}
        <section className="console-panel controls-panel" aria-label="Experiment controller">
          <div className="panel-header">
            <div className="panel-title-group">
              <Sliders size={16} className="panel-icon" />
              <h2 className="panel-title">Experiment controller</h2>
            </div>
            <StatusBadge status={isRunning ? 'running' : 'idle'} label={isRunning ? 'Optimization in progress' : 'Ready'} />
          </div>

          {/* Active study context & runtime telemetry */}
          <div className="controls-context-box">
            <div className="controls-context-row">
              <span className="controls-context-label">Target application</span>
              <span className="controls-context-value">
                {adapters?.find(a => a.is_default)?.application || adapters?.[0]?.application || 'Finance RAG (Internal)'}
              </span>
            </div>
            <div className="controls-context-row">
              <span className="controls-context-label">Optimization engine</span>
              <span className="controls-context-value mono-nums">
                TPE / Bayesian (Optuna)
              </span>
            </div>
            <div className="controls-context-row">
              <span className="controls-context-label">Objective metric</span>
              <span className="controls-context-value mono-nums" style={{ color: 'var(--color-cool)' }}>
                Composite score (Accuracy + Latency)
              </span>
            </div>
            <div className="controls-context-row">
              <span className="controls-context-label">Telemetry recorded</span>
              <span className="controls-context-value mono-nums">
                {iterations.length} trials in study
              </span>
            </div>
          </div>

          <div className="controls-form">
            <div className="controls-top-bar">
              <label className="input-field-label" htmlFor="eval-budget-input">
                Evaluation budget (iterations)
              </label>
              <button
                type="button"
                className="console-btn-wizard"
                onClick={() => setIsWizardOpen(true)}
                disabled={isRunning}
                title="Open comprehensive Experiment Configuration Wizard"
              >
                <SlidersHorizontal size={13} />
                <span>Experiment wizard</span>
              </button>
            </div>
            <div className="controls-action-row">
              <input
                id="eval-budget-input"
                type="number"
                className="console-number-input"
                value={runCount}
                onChange={(e) => setRunCount(Math.max(1, parseInt(e.target.value) || 1))}
                disabled={isRunning}
                min="1"
                max="50"
                aria-label="Evaluation budget iterations"
              />

              <button
                type="button"
                className="console-btn-primary"
                onClick={() => onStartRun()}
                disabled={isRunning}
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="animate-spin" size={15} />
                    <span>Tuning…</span>
                  </>
                ) : (
                  <>
                    <Play size={15} />
                    <span>Quick run</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="console-btn-secondary"
                onClick={onDownloadReport || (() => { window.location.href = '/report/current'; })}
                disabled={isRunning || iterations.length === 0}
                title="Download Markdown summary report"
              >
                <Download size={15} />
                <span>Report</span>
              </button>
            </div>
          </div>

          {errorMsg && (
            <div className="error-callout" role="alert">
              <AlertCircle size={14} />
              <span>{errorMsg}</span>
            </div>
          )}
        </section>

        {/* Current Champion Configuration Card */}
        <section className="console-panel champion-panel" aria-label="Current champion configuration">
          <div className="panel-header">
            <div className="panel-title-group">
              <Activity size={16} className="panel-icon" />
              <h2 className="panel-title">Current champion configuration</h2>
            </div>
            {bestConfig && (
              <span className="champion-badge">
                Active champion
              </span>
            )}
          </div>

          {bestConfig ? (
            <div className="champion-content">
              {/* Stat tiles row */}
              <div className="champion-metrics-grid">
                <div className="champion-metric-tile">
                  <span className="champion-metric-num">
                    {typeof bestConfig.score === 'number' ? bestConfig.score.toFixed(4) : '---'}
                  </span>
                  <span className="champion-metric-label">Tuning accuracy</span>
                </div>

                <div className="champion-metric-tile highlight-cool">
                  <span className="champion-metric-num" style={{ color: 'var(--color-cool)' }}>
                    {typeof bestConfig.composite_score === 'number' ? bestConfig.composite_score.toFixed(4) : '---'}
                  </span>
                  <span className="champion-metric-label">Composite score</span>
                </div>

                <div className="champion-metric-tile">
                  <span className="champion-metric-num" style={{ color: 'var(--color-sage)' }}>
                    {holdoutScore !== null && holdoutScore !== undefined ? holdoutScore.toFixed(4) : '---'}
                  </span>
                  <span className="champion-metric-label">Holdout accuracy</span>
                </div>

                <div className="champion-metric-tile">
                  <span className="champion-metric-num">
                    {typeof bestConfig.avg_latency_ms === 'number' && bestConfig.avg_latency_ms > 0
                      ? `${bestConfig.avg_latency_ms.toFixed(0)}ms`
                      : '---'}
                  </span>
                  <span className="champion-metric-label">Average latency</span>
                </div>

                <div className="champion-metric-tile">
                  <span className="champion-metric-num">
                    {typeof bestConfig.total_tokens === 'number' && bestConfig.total_tokens > 0
                      ? bestConfig.total_tokens.toLocaleString()
                      : '---'}
                  </span>
                  <span className="champion-metric-label">Total tokens</span>
                </div>
              </div>

              {/* Active parameters grid */}
              <div className="champion-params-grid">
                {bestConfig.config && Object.entries(bestConfig.config).map(([k, v]) => {
                  if (k === 'prompt_template') return null;
                  return (
                    <div className="champion-param-item" key={k}>
                      <span className="param-item-key">{k}</span>
                      <span className="param-item-val">{String(v)}</span>
                    </div>
                  );
                })}
              </div>

              {/* Prompt template preview if configured */}
              {bestConfig.config?.prompt_template && (
                <div className="prompt-preview-block" title="Current prompt template">
                  <span className="prompt-preview-label">Prompt template</span>
                  <pre className="prompt-preview-text">{bestConfig.config.prompt_template}</pre>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-panel-body">
              <EmptyState
                title="No champion evaluated yet"
                description="Trigger an optimization cycle above to begin Bayesian parameter exploration."
              />
            </div>
          )}
        </section>
      </div>

      {/* Main Section Grid: Progress View (Chart/Table) + Iteration Feed */}
      <div className="workspace-main-grid">
        {/* Left Column: Progress Chart / Table */}
        <section className="console-panel progress-panel" aria-label="Optimization progress">
          <div className="panel-header">
            <div className="panel-title-group">
              <h2 className="panel-title">Optimization progress</h2>
              {viewMode === 'table' && selectedIters.length === 2 && (
                <button
                  type="button"
                  className="console-btn-compare"
                  onClick={() => setShowCompareModal(true)}
                  aria-label="Compare 2 selected iterations"
                >
                  <GitCompare size={14} />
                  <span>Compare (2 selected)</span>
                </button>
              )}
            </div>

            <div className="segmented-tab-control" role="tablist" aria-label="Progress view mode">
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === 'chart'}
                className={`segmented-tab-btn ${viewMode === 'chart' ? 'is-active' : ''}`}
                onClick={() => setViewMode('chart')}
              >
                Chart
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === 'table'}
                className={`segmented-tab-btn ${viewMode === 'table' ? 'is-active' : ''}`}
                onClick={() => setViewMode('table')}
              >
                Table
              </button>
            </div>
          </div>

          <div className="panel-body">
            {chartData.length > 0 ? (
              viewMode === 'chart' ? (
                <div className="chart-container" style={{ width: '100%', height: '340px' }}>
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
                      {/* Secondary line: Accuracy */}
                      <Line
                        type="monotone"
                        dataKey="score"
                        name="Accuracy"
                        stroke="var(--color-cool-soft)"
                        strokeWidth={1.5}
                        strokeDasharray="3 3"
                        dot={false}
                        activeDot={{ r: 4, strokeWidth: 0, fill: 'var(--color-cool-soft)' }}
                      />
                      {/* Primary line: Composite Score */}
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
                              key={`${payload.iteration}-composite-milestone`}
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
                <div className="table-wrapper-block">
                  {/* Table Filter Toolbar */}
                  <div className="table-filter-toolbar">
                    <div className="toolbar-search-box">
                      <Search size={13} style={{ color: 'var(--color-muted)' }} />
                      <input
                        type="text"
                        className="console-search-input"
                        placeholder="Search parameters or hypotheses…"
                        value={searchQuery}
                        onChange={e => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                      />
                    </div>

                    <div className="toolbar-filter-group">
                      {experimentsList.length > 0 && (
                        <select
                          className="console-select-input"
                          value={selectedExperimentId}
                          onChange={e => { setSelectedExperimentId(e.target.value); setCurrentPage(1); }}
                          aria-label="Filter by experiment study"
                        >
                          <option value="all">All studies ({experimentsList.length})</option>
                          {experimentsList.map(exp => (
                            <option key={exp.experiment_id} value={exp.experiment_id}>
                              {exp.name || exp.experiment_id} ({exp.total_trials} trials)
                            </option>
                          ))}
                        </select>
                      )}

                      <div className="diff-filter-tabs" role="tablist" aria-label="Status filters">
                        <button
                          type="button"
                          role="tab"
                          aria-selected={statusFilter === 'all'}
                          className={`diff-tab-btn ${statusFilter === 'all' ? 'is-active' : ''}`}
                          onClick={() => { setStatusFilter('all'); setCurrentPage(1); }}
                        >
                          All
                        </button>
                        <button
                          type="button"
                          role="tab"
                          aria-selected={statusFilter === 'accepted'}
                          className={`diff-tab-btn ${statusFilter === 'accepted' ? 'is-active' : ''}`}
                          onClick={() => { setStatusFilter('accepted'); setCurrentPage(1); }}
                        >
                          Accepted
                        </button>
                        <button
                          type="button"
                          role="tab"
                          aria-selected={statusFilter === 'rejected'}
                          className={`diff-tab-btn ${statusFilter === 'rejected' ? 'is-active' : ''}`}
                          onClick={() => { setStatusFilter('rejected'); setCurrentPage(1); }}
                        >
                          Rejected
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="table-scroll-container">
                    <table className="console-table" aria-label="Trial iterations table">
                      <thead>
                        <tr>
                          <th style={{ width: '48px', textAlign: 'center' }}>Select</th>
                          <th style={{ width: '60px' }}>Iter #</th>
                          <th>Parameter tuned</th>
                          <th>Accuracy</th>
                          <th>Latency</th>
                          <th>Tokens</th>
                          <th>Composite</th>
                          <th style={{ width: '90px' }}>Status</th>
                          <th style={{ width: '48px', textAlign: 'center' }}>Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedRows.map((item) => {
                          const isSelected = selectedIters.includes(item.iteration_number);
                          const isDisabled = isCheckboxDisabled(item.iteration_number);
                          const scores = {
                            newAcc: item.new_score,
                            newComp: item.composite_score !== undefined && item.composite_score !== null ? item.composite_score : item.new_score,
                            oldAcc: item.old_score,
                          };
                          return (
                            <tr
                              key={item.iteration_number}
                              className={`${isSelected ? 'row-selected' : ''} ${item.accepted ? 'row-accepted' : 'row-rejected'} eval-tr-clickable`}
                              onClick={() => setSelectedTrial(item)}
                              tabIndex={0}
                              onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && setSelectedTrial(item)}
                            >
                              <td style={{ textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  disabled={isDisabled}
                                  onChange={() => handleToggleSelect(item.iteration_number)}
                                  className="console-checkbox"
                                  aria-label={`Select iteration ${item.iteration_number} for comparison`}
                                />
                              </td>
                              <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                                #{item.iteration_number}
                              </td>
                              <td>
                                {item.param === '[Baseline]' || item.param === 'None' || item.proposal_status === 'baseline' || item.proposal_status === 'infrastructure_error' ? (
                                  <span style={{ color: 'var(--color-muted)' }}>Baseline setup</span>
                                ) : item.param === '[Unavailable]' || item.proposal_status === 'failed_proposal' ? (
                                  <span style={{ color: 'var(--color-bad)' }}>Proposal unavailable</span>
                                ) : item.proposal_status === 'invalid_proposal' ? (
                                  <span style={{ color: 'var(--color-accent)' }}>Rejected proposal ({item.param})</span>
                                ) : (
                                  <span className="param-name-tag">{item.param}</span>
                                )}
                              </td>
                              <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                                {item.param === '[Baseline]' || item.param === 'None' || item.iteration_number === 0 || item.proposal_status === 'baseline' ? (
                                  scores.newAcc.toFixed(4)
                                ) : item.param === '[Unavailable]' || item.proposal_status === 'failed_proposal' ? (
                                  `${scores.newAcc.toFixed(3)} (N/A)`
                                ) : (
                                  `${scores.oldAcc.toFixed(3)} → ${scores.newAcc.toFixed(3)}`
                                )}
                              </td>
                              <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                                {item.avg_latency_ms > 0 ? `${item.avg_latency_ms.toFixed(0)}ms` : '---'}
                              </td>
                              <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                                {item.total_tokens > 0 ? item.total_tokens.toLocaleString() : '---'}
                              </td>
                              <td style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
                                {scores.newComp.toFixed(4)}
                              </td>
                              <td>
                                <StatusBadge
                                  status={item.accepted ? 'accepted' : 'rejected'}
                                  label={item.accepted ? 'Accepted' : 'Rejected'}
                                />
                              </td>
                              <td style={{ textAlign: 'center' }} onClick={e => { e.stopPropagation(); setSelectedTrial(item); }}>
                                <button
                                  type="button"
                                  className="console-row-inspect-btn"
                                  title="Inspect trial details"
                                  aria-label={`Inspect trial ${item.iteration_number}`}
                                >
                                  <Eye size={13} />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Bar */}
                  <div className="table-pagination-bar">
                    <span className="pagination-info mono-nums">
                      Showing {filteredTableRows.length === 0 ? 0 : Math.min(filteredTableRows.length, (currentPage - 1) * pageSize + 1)} to {Math.min(filteredTableRows.length, currentPage * pageSize)} of {filteredTableRows.length} trials
                    </span>
                    <div className="pagination-btn-group">
                      <button
                        type="button"
                        className="pagination-btn"
                        disabled={currentPage <= 1}
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        aria-label="Previous page"
                      >
                        <ChevronLeft size={14} />
                      </button>
                      <span className="pagination-page-indicator mono-nums">
                        Page {currentPage} of {totalPages}
                      </span>
                      <button
                        type="button"
                        className="pagination-btn"
                        disabled={currentPage >= totalPages}
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        aria-label="Next page"
                      >
                        <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              )
            ) : (
              <div className="empty-panel-body">
                <EmptyState
                  title="Waiting for trial run"
                  description="Click “Run optimization” above to begin exploring RAG parameters."
                />
              </div>
            )}
          </div>
        </section>

        {/* Right Column: Iteration Diagnostic Log */}
        <section className="console-panel feed-panel" aria-label="Iteration diagnostic log">
          <div className="panel-header">
            <div className="panel-title-group">
              <h2 className="panel-title">Iteration diagnostic log</h2>
              <span className="item-count-badge">
                {iterations.length} {iterations.length === 1 ? 'record' : 'records'}
              </span>
            </div>
          </div>

          <div className="feed-scroll-container">
            {iterations.length > 0 ? (
              iterations.map((item) => {
                const newAcc = item.new_score;
                const newComp = item.composite_score !== undefined && item.composite_score !== null
                  ? item.composite_score
                  : item.new_score;

                let oldAcc = item.old_score;
                let oldComp = item.old_score;

                const isBaseline = item.param === '[Baseline]' || item.param === 'None' || item.iteration_number === 0 || item.proposal_status === 'baseline' || item.proposal_status === 'infrastructure_error';
                const isFailedProposal = item.proposal_status === 'failed_proposal' || item.param === '[Unavailable]';
                const isInvalidProposal = item.proposal_status === 'invalid_proposal';

                if (!isBaseline && item.iteration_number > 0) {
                  const prevAccepted = iterations.find(
                    (it) => it.iteration_number < item.iteration_number && it.accepted && (!item.experiment_id || it.experiment_id === item.experiment_id)
                  );
                  if (prevAccepted) {
                    oldAcc = prevAccepted.new_score;
                    oldComp = prevAccepted.composite_score !== undefined && prevAccepted.composite_score !== null
                      ? prevAccepted.composite_score
                      : prevAccepted.new_score;
                  }
                }

                return (
                  <article
                    key={item.iteration_number}
                    className={`diagnostic-card ${item.accepted ? 'is-accepted' : 'is-rejected'}`}
                  >
                    <div className="diagnostic-header">
                      <div className="diagnostic-title-group">
                        <span className="diagnostic-iter-num">
                          Iteration #{item.iteration_number}
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
                        {typeof item.total_tokens === 'number' && item.total_tokens > 0 && (
                          <span className="diagnostic-telemetry-tag">
                            <Coins size={11} />
                            <span>{item.total_tokens.toLocaleString()} tokens</span>
                          </span>
                        )}
                      </div>
                      <span className="diagnostic-timestamp">{item.timestamp}</span>
                    </div>

                    {item.hypothesis && !isBaseline && (
                      <blockquote className="diagnostic-hypothesis">
                        “{item.hypothesis}”
                      </blockquote>
                    )}

                    {item.motivated_by && !isBaseline && (
                      <div className="diagnostic-motivated-tag">
                        <span style={{ fontWeight: 500 }}>Targeting:</span> {item.motivated_by.split(' | ').join(', ')}
                      </div>
                    )}

                    <div className="diagnostic-diff-row">
                      <div className="diff-param-box">
                        {isBaseline ? (
                          <span style={{ color: 'var(--color-cool)', fontWeight: 500 }}>
                            {item.proposal_status === 'infrastructure_error' ? 'Baseline failed (provider offline)' : 'Baseline setup'}
                          </span>
                        ) : isFailedProposal ? (
                          <span style={{ color: 'var(--color-bad)', fontWeight: 500 }}>
                            Proposal unavailable
                          </span>
                        ) : isInvalidProposal ? (
                          <span style={{ color: 'var(--color-accent)', fontWeight: 500 }}>
                            Validation rejected ({item.param})
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
                          <span className="diff-score-label">Acc:</span>
                          {isBaseline || isFailedProposal ? (
                            <span className="diff-score-num">{newAcc.toFixed(4)}</span>
                          ) : (
                            <div className="diff-score-progress">
                              <span className="diff-score-num">{oldAcc.toFixed(3)}</span>
                              <span className="diff-arrow">→</span>
                              <span className="diff-score-num highlight">{newAcc.toFixed(3)}</span>
                            </div>
                          )}
                        </div>
                        <div className="diff-score-item">
                          <span className="diff-score-label">Comp:</span>
                          {isBaseline || isFailedProposal ? (
                            <span className="diff-score-num">{newComp.toFixed(4)}</span>
                          ) : (
                            <div className="diff-score-progress">
                              <span className="diff-score-num">{oldComp.toFixed(3)}</span>
                              <span className="diff-arrow">→</span>
                              <span className="diff-score-num highlight">{newComp.toFixed(3)}</span>
                            </div>
                          )}
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
                  title="No iterations logged yet"
                  description="Run an optimization cycle to observe real-time agent diagnostics and Optuna trials."
                />
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Comparison Modal Overlay */}
      {showCompareModal && iterA && iterB && (
        <div
          className="console-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="compare-modal-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowCompareModal(false);
          }}
        >
          <div className="console-modal-card">
            <div className="modal-header">
              <div className="modal-title-group">
                <GitCompare size={18} className="panel-icon" />
                <h3 id="compare-modal-title" className="modal-title">Configuration comparison</h3>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowCompareModal(false)}
                aria-label="Close comparison modal"
              >
                <X size={16} />
              </button>
            </div>

            <div className="modal-content-scroll">
              {/* Header column split */}
              <div className="compare-split-header">
                <div className="compare-col-header">
                  <h4>Iteration #{iterA.iteration_number}</h4>
                  <StatusBadge
                    status={iterA.accepted ? 'accepted' : 'rejected'}
                    label={iterA.accepted ? 'Accepted' : 'Rejected'}
                  />
                </div>
                <div className="compare-col-header">
                  <h4>Iteration #{iterB.iteration_number}</h4>
                  <StatusBadge
                    status={iterB.accepted ? 'accepted' : 'rejected'}
                    label={iterB.accepted ? 'Accepted' : 'Rejected'}
                  />
                </div>
              </div>

              {/* Hypotheses comparison */}
              <div className="compare-hypotheses-box">
                <div className="compare-hyp-col">
                  <span className="compare-section-label">Diagnostic hypothesis</span>
                  <p className="compare-hyp-body">“{iterA.hypothesis || 'Baseline setup'}”</p>
                  {iterA.motivated_by && (
                    <span className="compare-mot-tag">Targeting: {iterA.motivated_by}</span>
                  )}
                </div>
                <div className="compare-hyp-col">
                  <span className="compare-section-label">Diagnostic hypothesis</span>
                  <p className="compare-hyp-body">“{iterB.hypothesis || 'Baseline setup'}”</p>
                  {iterB.motivated_by && (
                    <span className="compare-mot-tag">Targeting: {iterB.motivated_by}</span>
                  )}
                </div>
              </div>

              {/* Metrics Comparison Table */}
              <div className="compare-section">
                <span className="compare-section-label">Evaluation metrics</span>
                <div className="compare-metrics-grid">
                  <div className="compare-metric-row">
                    <span className="compare-metric-name">Accuracy score</span>
                    <span className="compare-metric-val">{iterA.new_score.toFixed(4)}</span>
                    <span className="compare-metric-val">{iterB.new_score.toFixed(4)}</span>
                  </div>

                  <div className="compare-metric-row">
                    <span className="compare-metric-name">Composite score</span>
                    <span className="compare-metric-val" style={{ color: 'var(--color-cool)' }}>
                      {(iterA.composite_score !== undefined && iterA.composite_score !== null ? iterA.composite_score : iterA.new_score).toFixed(4)}
                    </span>
                    <span className="compare-metric-val" style={{ color: 'var(--color-cool)' }}>
                      {(iterB.composite_score !== undefined && iterB.composite_score !== null ? iterB.composite_score : iterB.new_score).toFixed(4)}
                    </span>
                  </div>

                  <div className="compare-metric-row">
                    <span className="compare-metric-name">Average latency</span>
                    <span className="compare-metric-val">
                      {iterA.avg_latency_ms > 0 ? `${iterA.avg_latency_ms.toFixed(0)}ms` : '---'}
                    </span>
                    <span className="compare-metric-val">
                      {iterB.avg_latency_ms > 0 ? `${iterB.avg_latency_ms.toFixed(0)}ms` : '---'}
                    </span>
                  </div>

                  <div className="compare-metric-row">
                    <span className="compare-metric-name">Total tokens</span>
                    <span className="compare-metric-val">
                      {iterA.total_tokens > 0 ? iterA.total_tokens.toLocaleString() : '---'}
                    </span>
                    <span className="compare-metric-val">
                      {iterB.total_tokens > 0 ? iterB.total_tokens.toLocaleString() : '---'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Pipeline Parameters Comparison Table */}
              <div className="compare-section">
                <span className="compare-section-label">Pipeline parameters</span>
                <table className="compare-params-table">
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left' }}>Parameter</th>
                      <th>Iter #{iterA.iteration_number} value</th>
                      <th>Iter #{iterB.iteration_number} value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {renderConfigCompareRow('Chunk size', 'chunk_size')}
                    {renderConfigCompareRow('Chunk overlap', 'chunk_overlap')}
                    {renderConfigCompareRow('Top K', 'top_k')}
                    {renderConfigCompareRow('Temperature', 'temperature')}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Experiment Configuration Wizard */}
      <ExperimentWizard
        isOpen={isWizardOpen}
        onClose={() => setIsWizardOpen(false)}
        onLaunch={onStartRun}
        adapters={adapters}
        isSystemRunning={isRunning}
      />

      {/* Trial Detail Inspection Drawer */}
      {selectedTrial && (
        <TrialDetailDrawer
          trial={selectedTrial}
          onClose={() => setSelectedTrial(null)}
        />
      )}
    </div>
  );
}

