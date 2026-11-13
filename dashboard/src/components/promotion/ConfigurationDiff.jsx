import React, { useState, useMemo } from 'react';
import { 
  ArrowRight, Check, SlidersHorizontal, Plus, Minus, 
  Equal, ArrowUpRight, ArrowDownRight, Layers
} from 'lucide-react';
import StatusBadge from '../common/StatusBadge';

export default function ConfigurationDiff({
  baselineConfig = {},
  candidateConfig = {},
  baselineMetrics = null,
  candidateMetrics = null,
  title = "Parameter configuration differential"
}) {
  const [userSelectedFilter, setUserSelectedFilter] = useState(null);

  // Parameter diff analysis
  const diffItems = useMemo(() => {
    const base = baselineConfig || {};
    const cand = candidateConfig || {};
    const allKeys = Array.from(new Set([...Object.keys(base), ...Object.keys(cand)])).sort();

    return allKeys.map(key => {
      const hasBase = Object.prototype.hasOwnProperty.call(base, key);
      const hasCand = Object.prototype.hasOwnProperty.call(cand, key);
      const oldVal = base[key];
      const newVal = cand[key];

      let type = 'unchanged';
      if (!hasBase && hasCand) {
        type = 'added';
      } else if (hasBase && !hasCand) {
        type = 'removed';
      } else if (JSON.stringify(oldVal) !== JSON.stringify(newVal)) {
        type = 'modified';
      }

      // Compute numerical delta if applicable
      let numericDelta = null;
      if (typeof oldVal === 'number' && typeof newVal === 'number') {
        numericDelta = newVal - oldVal;
      }

      return {
        key,
        oldVal,
        newVal,
        type,
        numericDelta
      };
    });
  }, [baselineConfig, candidateConfig]);

  const counts = useMemo(() => {
    const modified = diffItems.filter(d => d.type === 'modified').length;
    const added = diffItems.filter(d => d.type === 'added').length;
    const removed = diffItems.filter(d => d.type === 'removed').length;
    const unchanged = diffItems.filter(d => d.type === 'unchanged').length;
    const totalChanged = modified + added + removed;
    return { modified, added, removed, unchanged, totalChanged, total: diffItems.length };
  }, [diffItems]);

  // If user hasn't chosen a filter, default to 'changed' if any exist, otherwise 'all'
  const filterMode = userSelectedFilter || (counts.totalChanged > 0 ? 'changed' : 'all');

  const filteredItems = useMemo(() => {
    if (filterMode === 'changed') {
      return diffItems.filter(d => d.type !== 'unchanged');
    }
    if (filterMode === 'unchanged') {
      return diffItems.filter(d => d.type === 'unchanged');
    }
    return diffItems;
  }, [diffItems, filterMode]);

  // Format parameter value
  const formatVal = (v) => {
    if (v === null || v === undefined) return 'None';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (typeof v === 'number') return v.toString();
    if (typeof v === 'object') return JSON.stringify(v);
    return String(v);
  };

  return (
    <div className="console-panel config-diff-panel">
      {/* Header and Filter Controls */}
      <div className="diff-header-row">
        <div className="diff-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
            <SlidersHorizontal size={16} style={{ color: 'var(--color-cool)' }} />
            <h3 className="diff-section-heading">{title}</h3>
          </div>
          <span className="diff-subtitle">
            Exact parameter differences between active production and the optimization champion.
          </span>
        </div>

        <div className="diff-filter-tabs" role="tablist" aria-label="Diff view filters">
          <button
            type="button"
            role="tab"
            aria-selected={filterMode === 'changed'}
            className={`diff-tab-btn ${filterMode === 'changed' ? 'is-active' : ''}`}
            onClick={() => setUserSelectedFilter('changed')}
            title="Show only parameters with modified, added, or removed values"
          >
            <span>Changed</span>
            <span className="diff-count-pill mono-nums">{counts.totalChanged}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filterMode === 'all'}
            className={`diff-tab-btn ${filterMode === 'all' ? 'is-active' : ''}`}
            onClick={() => setUserSelectedFilter('all')}
            title="Show all pipeline configuration parameters"
          >
            <span>All parameters</span>
            <span className="diff-count-pill mono-nums">{counts.total}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filterMode === 'unchanged'}
            className={`diff-tab-btn ${filterMode === 'unchanged' ? 'is-active' : ''}`}
            onClick={() => setUserSelectedFilter('unchanged')}
            title="Show parameters that are identical between baseline and candidate"
          >
            <span>Unchanged</span>
            <span className="diff-count-pill mono-nums">{counts.unchanged}</span>
          </button>
        </div>
      </div>

      {/* Filter Explanation & Zero-Diff Status Banner */}
      {counts.totalChanged === 0 && (
        <div style={{
          padding: 'var(--space-2xs) var(--space-sm)',
          background: 'var(--color-paper-1)',
          border: 'var(--rule-hair) solid var(--color-rule)',
          borderRadius: 'var(--radius-sm)',
          fontSize: 'var(--text-2xs)',
          color: 'var(--color-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-xs)'
        }}>
          <Equal size={12} style={{ color: 'var(--color-sage)' }} />
          <span>
            <strong>In sync:</strong> Active production and champion configurations currently have identical parameter values. Showing all {counts.total} active parameters.
          </span>
        </div>
      )}

      {/* Metric Delta Comparison Strip (if metrics provided) */}
      {(baselineMetrics || candidateMetrics) && (
        <div className="diff-metrics-strip">
          <div className="diff-metric-tile">
            <span className="diff-metric-label">Composite score</span>
            <div className="diff-metric-comparison">
              <span className="diff-metric-base mono-nums">
                {baselineMetrics?.composite_score?.toFixed(4) || '---'}
              </span>
              <ArrowRight size={12} className="diff-metric-arrow" />
              <span className="diff-metric-cand mono-nums" style={{ color: 'var(--color-cool)' }}>
                {candidateMetrics?.composite_score?.toFixed(4) || '---'}
              </span>
              {typeof candidateMetrics?.composite_score === 'number' && typeof baselineMetrics?.composite_score === 'number' && (
                <span className={`diff-delta-chip mono-nums ${candidateMetrics.composite_score >= baselineMetrics.composite_score ? 'positive' : 'negative'}`}>
                  {candidateMetrics.composite_score >= baselineMetrics.composite_score ? '+' : ''}
                  {(candidateMetrics.composite_score - baselineMetrics.composite_score).toFixed(4)}
                </span>
              )}
            </div>
          </div>

          <div className="diff-metric-tile">
            <span className="diff-metric-label">Tuning accuracy</span>
            <div className="diff-metric-comparison">
              <span className="diff-metric-base mono-nums">
                {baselineMetrics?.score ? (baselineMetrics.score * 100).toFixed(1) + '%' : '---'}
              </span>
              <ArrowRight size={12} className="diff-metric-arrow" />
              <span className="diff-metric-cand mono-nums" style={{ color: 'var(--color-sage)' }}>
                {candidateMetrics?.score ? (candidateMetrics.score * 100).toFixed(1) + '%' : '---'}
              </span>
              {typeof candidateMetrics?.score === 'number' && typeof baselineMetrics?.score === 'number' && (
                <span className={`diff-delta-chip mono-nums ${candidateMetrics.score >= baselineMetrics.score ? 'positive' : 'negative'}`}>
                  {candidateMetrics.score >= baselineMetrics.score ? '+' : ''}
                  {((candidateMetrics.score - baselineMetrics.score) * 100).toFixed(1)}%
                </span>
              )}
            </div>
          </div>

          <div className="diff-metric-tile">
            <span className="diff-metric-label">Mean latency</span>
            <div className="diff-metric-comparison">
              <span className="diff-metric-base mono-nums">
                {baselineMetrics?.avg_latency_ms ? baselineMetrics.avg_latency_ms.toFixed(0) + 'ms' : '---'}
              </span>
              <ArrowRight size={12} className="diff-metric-arrow" />
              <span className="diff-metric-cand mono-nums">
                {candidateMetrics?.avg_latency_ms ? candidateMetrics.avg_latency_ms.toFixed(0) + 'ms' : '---'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Table of Parameter Diffs */}
      <div className="diff-table-container">
        {filteredItems.length === 0 ? (
          <div className="diff-empty-slate">
            <Check size={16} style={{ color: 'var(--color-sage)' }} />
            <span>No parameter differences matching this filter. Candidate and baseline are identical.</span>
          </div>
        ) : (
          <table className="diff-table" aria-label="Parameter differential table">
            <thead>
              <tr>
                <th scope="col" style={{ width: '28%' }}>Parameter</th>
                <th scope="col" style={{ width: '16%' }}>Differential</th>
                <th scope="col" style={{ width: '26%' }}>Active baseline</th>
                <th scope="col" style={{ width: '4%' }}></th>
                <th scope="col" style={{ width: '26%' }}>Champion candidate</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map(item => {
                const isMod = item.type === 'modified';
                const isAdd = item.type === 'added';
                const isRem = item.type === 'removed';

                return (
                  <tr key={item.key} className={`diff-tr ${item.type}`}>
                    <td className="diff-td-param">
                      <span className="diff-param-code mono-nums">{item.key}</span>
                    </td>
                    <td className="diff-td-status">
                      {isMod && (
                        <span className="diff-tag mod">
                          <SlidersHorizontal size={10} /> Modified
                        </span>
                      )}
                      {isAdd && (
                        <span className="diff-tag add">
                          <Plus size={10} /> Added
                        </span>
                      )}
                      {isRem && (
                        <span className="diff-tag rem">
                          <Minus size={10} /> Removed
                        </span>
                      )}
                      {item.type === 'unchanged' && (
                        <span className="diff-tag unch">
                          <Equal size={10} /> Unchanged
                        </span>
                      )}
                    </td>
                    <td className="diff-td-val base">
                      <span className={`diff-val-box ${isMod ? 'is-old' : ''} mono-nums`}>
                        {isAdd ? '(none)' : formatVal(item.oldVal)}
                      </span>
                    </td>
                    <td className="diff-td-arrow">
                      {isMod ? <ArrowRight size={13} style={{ color: 'var(--color-cool)' }} /> : null}
                    </td>
                    <td className="diff-td-val cand">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2xs)' }}>
                        <span className={`diff-val-box ${isMod ? 'is-new' : ''} mono-nums`}>
                          {isRem ? '(none)' : formatVal(item.newVal)}
                        </span>
                        {item.numericDelta !== null && item.numericDelta !== 0 && (
                          <span className={`diff-inline-delta mono-nums ${item.numericDelta > 0 ? 'pos' : 'neg'}`}>
                            {item.numericDelta > 0 ? `+${item.numericDelta}` : item.numericDelta}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
