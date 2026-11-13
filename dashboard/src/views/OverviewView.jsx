import React from 'react';
import { 
  Layers, 
  FlaskConical, 
  CheckCircle2, 
  Clock, 
  TrendingUp, 
  RefreshCw,
  GitCommit,
  ArrowRight
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip 
} from 'recharts';
import MetricCard from '../components/common/MetricCard';
import StatusBadge from '../components/common/StatusBadge';
import LoadingState from '../components/common/LoadingState';
import EmptyState from '../components/common/EmptyState';
import ErrorState from '../components/common/ErrorState';

export default function OverviewView({ 
  summary, 
  health, 
  iterations = [], 
  loading, 
  error, 
  onRefresh,
  onNavigate
}) {
  if (loading) {
    return <LoadingState message="Fetching live experiment summaries and telemetry..." />;
  }

  if (error) {
    return <ErrorState error={error} onRetry={onRefresh} />;
  }

  const chartData = [...iterations]
    .filter(it => it.proposal_status !== 'failed_proposal' && typeof it.iteration_number === 'number')
    .sort((a, b) => a.iteration_number - b.iteration_number)
    .map(it => ({
      iteration: it.iteration_number,
      score: typeof it.new_score === 'number' ? parseFloat(it.new_score.toFixed(4)) : 0,
      composite: typeof it.composite_score === 'number' ? parseFloat(it.composite_score.toFixed(4)) : (typeof it.new_score === 'number' ? parseFloat(it.new_score.toFixed(4)) : 0),
      latency: typeof it.avg_latency_ms === 'number' ? it.avg_latency_ms : 0,
      accepted: it.accepted === 1 || it.accepted === true
    }));

  const CustomChartTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div
          style={{
            background: 'var(--color-paper-3)',
            border: 'var(--rule-hair) solid var(--color-rule-2)',
            borderRadius: 'var(--radius-pill)',
            padding: 'var(--space-xs) var(--space-sm)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-ink)',
            display: 'flex',
            flexDirection: 'column',
            gap: '3px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-md)' }}>
            <span style={{ color: 'var(--color-muted)' }}>Iteration</span>
            <span style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>#{data.iteration}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-md)' }}>
            <span style={{ color: 'var(--color-muted)' }}>Composite score</span>
            <span style={{ color: 'var(--color-cool)', fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
              {data.composite.toFixed(4)}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-md)' }}>
            <span style={{ color: 'var(--color-muted)' }}>Tuning accuracy</span>
            <span style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
              {data.score.toFixed(4)}
            </span>
          </div>
          {data.latency > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-md)' }}>
              <span style={{ color: 'var(--color-muted)' }}>Avg latency</span>
              <span style={{ fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
                {Math.round(data.latency)}ms
              </span>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-md)', marginTop: '2px', paddingTop: '2px', borderTop: 'var(--rule-hair) solid var(--color-rule)' }}>
            <span style={{ color: 'var(--color-muted)' }}>Result</span>
            <span style={{ color: data.accepted ? 'var(--color-ok)' : 'var(--color-bad)', fontWeight: 500 }}>
              {data.accepted ? 'Accepted' : 'Rejected'}
            </span>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 500, color: 'var(--color-ink)', margin: 0, letterSpacing: 'var(--tracking-display)' }}>
            Platform overview
          </h1>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)', margin: '4px 0 0 0', maxWidth: '65ch' }}>
            System-wide optimization benchmarks, model health telemetry, and trial progression.
          </p>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2xs)',
              padding: 'var(--space-2xs) var(--space-sm)',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--color-paper-2)',
              border: 'var(--rule-hair) solid var(--color-rule-2)',
              color: 'var(--color-ink)',
              fontSize: 'var(--text-xs)',
              cursor: 'pointer',
              transition: 'border-color var(--dur-micro) var(--ease-out)'
            }}
            title="Refresh overview metrics"
          >
            <RefreshCw size={13} />
            <span>Refresh telemetry</span>
          </button>
        )}
      </div>

      {/* Top Telemetry Stat Tiles */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--space-sm)'
        }}
      >
        <MetricCard
          title="Experiments"
          value={summary?.total_experiments ?? 0}
          subtitle="Distinct optimization runs"
          icon={FlaskConical}
          color="var(--color-cool)"
        />
        <MetricCard
          title="Total trials"
          value={summary?.total_trials ?? 0}
          subtitle={`${summary?.completed_trials ?? 0} completed`}
          icon={Layers}
          color="var(--color-ink)"
        />
        <MetricCard
          title="Accepted trials"
          value={summary?.accepted_trials ?? 0}
          subtitle={`${summary?.rejected_trials ?? 0} rejected`}
          icon={CheckCircle2}
          color="var(--color-ok)"
        />
        <MetricCard
          title="Avg composite score"
          value={typeof summary?.average_evaluation_score === 'number' ? summary.average_evaluation_score.toFixed(4) : '---'}
          subtitle="Across completed trials"
          icon={TrendingUp}
          color="var(--color-cool)"
        />
        <MetricCard
          title="Avg latency"
          value={summary?.average_latency_ms ? `${(summary.average_latency_ms / 1000).toFixed(2)}s` : '---'}
          subtitle="Per benchmark dataset"
          icon={Clock}
          color="var(--color-muted)"
        />
      </div>

      {/* Main Grid: Progress Curve & Audit Trail */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: chartData.length > 0 ? '1.5fr 1fr' : '1fr',
          gap: 'var(--space-sm)'
        }}
      >
        {/* Progress Curve */}
        {chartData.length > 0 && (
          <div
            style={{
              background: 'var(--color-paper-2)',
              border: 'var(--rule-hair) solid var(--color-rule)',
              borderRadius: 'var(--radius-card)',
              padding: 'var(--space-md)',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-sm)' }}>
              <div>
                <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--color-ink)', margin: 0 }}>
                  Trial progression curve
                </h3>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)' }}>
                  Composite score and accuracy milestones across iterations
                </span>
              </div>
            </div>

            <div style={{ width: '100%', height: '240px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <CartesianGrid stroke="var(--color-rule)" strokeDasharray="" />
                  <XAxis 
                    dataKey="iteration" 
                    stroke="var(--color-muted)" 
                    fontSize={11} 
                    tickLine={false} 
                    fontFamily="var(--font-outlier)" 
                  />
                  <YAxis 
                    domain={[0.0, 1.0]} 
                    stroke="var(--color-muted)" 
                    fontSize={11} 
                    tickLine={false} 
                    fontFamily="var(--font-outlier)" 
                  />
                  <Tooltip content={<CustomChartTooltip />} />
                  <Line 
                    type="monotone" 
                    dataKey="score" 
                    stroke="var(--color-muted)" 
                    strokeWidth={1.5} 
                    dot={false} 
                    name="Accuracy" 
                  />
                  <Line 
                    type="monotone" 
                    dataKey="composite" 
                    stroke="var(--color-cool)" 
                    strokeWidth={2} 
                    dot={(props) => {
                      const { cx, cy, payload } = props;
                      if (!payload || !payload.accepted) return null;
                      return (
                        <circle 
                          key={`point-${payload.iteration}`}
                          cx={cx} 
                          cy={cy} 
                          r={3.5} 
                          fill="var(--color-ok)" 
                          stroke="none"
                        />
                      );
                    }}
                    name="Composite score" 
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Audit Trail: Recent Activity */}
        <div
          style={{
            background: 'var(--color-paper-2)',
            border: 'var(--rule-hair) solid var(--color-rule)',
            borderRadius: 'var(--radius-card)',
            padding: 'var(--space-md)',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-sm)' }}>
            <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--color-ink)', margin: 0 }}>
              Recent trials
            </h3>
            {onNavigate && (
              <button
                onClick={() => onNavigate('trials')}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-cool)',
                  fontSize: 'var(--text-xs)',
                  cursor: 'pointer',
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <span>View trial history</span>
                <ArrowRight size={12} />
              </button>
            )}
          </div>

          {summary?.recent_activity && summary.recent_activity.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {summary.recent_activity.map((it) => (
                <div
                  key={it.iteration_number}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-2xs) var(--space-xs)',
                    borderRadius: 'var(--radius-pill)',
                    background: 'var(--color-paper-3)',
                    border: 'var(--rule-hair) solid var(--color-rule)',
                    fontSize: 'var(--text-xs)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                    <span 
                      style={{ 
                        fontFamily: 'var(--font-outlier)', 
                        fontVariantNumeric: 'tabular-nums', 
                        color: 'var(--color-muted)',
                        minWidth: '28px' 
                      }}
                    >
                      #{it.iteration_number}
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ color: 'var(--color-ink)', fontWeight: 500 }}>
                        {it.param === '[Baseline]' ? 'Baseline setup' : it.param || 'Baseline'}
                      </span>
                      <span style={{ fontSize: '10px', color: 'var(--color-muted)', fontFamily: 'var(--font-outlier)' }}>
                        {it.timestamp ? it.timestamp.split(' ')[1] : ''}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                    <span style={{ fontFamily: 'var(--font-outlier)', color: 'var(--color-cool)', fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
                      {typeof it.composite_score === 'number' ? it.composite_score.toFixed(4) : '---'}
                    </span>
                    <StatusBadge
                      status={it.proposal_status === 'baseline' ? 'baseline' : (it.accepted ? 'accepted' : 'rejected')}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No recent activity" description="Run your first optimization experiment to see activity." />
          )}
        </div>
      </div>
    </div>
  );
}
