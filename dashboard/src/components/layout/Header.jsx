import React from 'react';
import { 
  Radio, 
  Download, 
  ExternalLink, 
  PanelLeft, 
  Cpu, 
  Server,
  Activity
} from 'lucide-react';

const PAGE_LABELS = {
  overview: 'Overview',
  applications: 'Applications',
  evaluations: 'Evaluations',
  experiments: 'Experiments',
  trials: 'Trial history',
  optimization: 'Engine configuration',
  promotions: 'Promotions & diffs',
  settings: 'Settings'
};

export default function Header({ 
  health, 
  activeApp = 'Finance RAG (Internal)', 
  activePage = 'overview',
  onDownloadReport, 
  wsStatus, 
  runStatus = 'idle',
  onNavigateHome,
  onToggleSidebar,
  isSidebarCollapsed
}) {
  const isHealthy = health && health.status === 'healthy';
  const isDegraded = health && health.status === 'degraded';
  
  let healthColor = 'var(--color-bad)';
  let healthLabel = 'Backend offline';
  if (isHealthy) {
    healthColor = 'var(--color-ok)';
    healthLabel = 'Providers online';
  } else if (isDegraded) {
    healthColor = 'var(--color-accent)';
    healthLabel = 'Providers degraded';
  } else if (health && health.backend === 'online') {
    healthColor = 'var(--color-accent)';
    healthLabel = 'Ollama offline';
  }

  const modelSummary = health?.optimizer?.model 
    ? `${health.optimizer.model} / ${health.generator?.model || 'llama3.2'}`
    : 'Local models';

  return (
    <header
      role="banner"
      style={{
        height: '56px',
        background: 'var(--color-paper-3)',
        borderBottom: 'var(--rule-hair) solid var(--color-rule)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 var(--space-md)',
        flexShrink: 0,
        gap: 'var(--space-sm)'
      }}
    >
      {/* Left: Sidebar toggle, breadcrumb, active target */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', minWidth: 0 }}>
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            aria-label={isSidebarCollapsed ? 'Expand navigation sidebar' : 'Collapse navigation sidebar'}
            title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--color-muted)',
              cursor: 'pointer',
              padding: '6px',
              display: 'flex',
              alignItems: 'center',
              borderRadius: 'var(--radius-pill)',
              transition: 'color var(--dur-micro) var(--ease-out)'
            }}
          >
            <PanelLeft size={16} />
          </button>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2xs)', fontSize: 'var(--text-sm)', whiteSpace: 'nowrap' }}>
          <span style={{ color: 'var(--color-muted)' }}>AutoTune</span>
          <span style={{ color: 'var(--color-rule-2)' }}>/</span>
          <span style={{ color: 'var(--color-ink)', fontWeight: 500 }}>
            {PAGE_LABELS[activePage] || activePage}
          </span>
        </div>

        <div 
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 'var(--space-2xs)', 
            fontSize: 'var(--text-xs)', 
            color: 'var(--color-muted)',
            padding: '2px 8px',
            background: 'var(--color-paper-2)',
            border: 'var(--rule-hair) solid var(--color-rule)',
            borderRadius: 'var(--radius-pill)',
            whiteSpace: 'nowrap'
          }}
          title="Active target RAG application"
        >
          <Server size={12} style={{ color: 'var(--color-cool)' }} />
          <span>target:</span>
          <span style={{ color: 'var(--color-ink)', fontFamily: 'var(--font-outlier)' }}>
            {activeApp}
          </span>
        </div>
      </div>

      {/* Right: Live WebSocket, Ollama status, actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', flexShrink: 0 }}>
        {/* WebSocket Stream Indicator */}
        <div 
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '4px', 
            fontSize: 'var(--text-xs)', 
            color: 'var(--color-muted)',
            padding: '3px 8px',
            borderRadius: 'var(--radius-pill)',
            background: 'var(--color-paper-2)',
            border: 'var(--rule-hair) solid var(--color-rule)'
          }} 
          title={`WebSocket stream status: ${wsStatus}`}
        >
          <Radio 
            size={11} 
            style={{ 
              color: runStatus === 'running' 
                ? 'var(--color-cool)' 
                : wsStatus === 'connected' 
                ? 'var(--color-ok)' 
                : wsStatus === 'reconnecting' 
                ? 'var(--color-accent)' 
                : 'var(--color-bad)',
              flexShrink: 0
            }} 
          />
          <span style={{ fontFamily: 'var(--font-outlier)' }}>
            {runStatus === 'running' 
              ? 'Optimizing' 
              : wsStatus === 'connected' 
              ? 'Telemetry live' 
              : wsStatus === 'reconnecting' 
              ? 'Reconnecting…' 
              : 'Telemetry offline'}
          </span>
        </div>

        {/* Real Ollama & Model Status */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            padding: '3px 8px',
            borderRadius: 'var(--radius-pill)',
            background: 'var(--color-paper-2)',
            border: 'var(--rule-hair) solid var(--color-rule)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-ink-2)'
          }}
          title={health?.errors?.join(', ') || `Models: ${modelSummary}`}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: healthColor,
              flexShrink: 0
            }}
          />
          <span style={{ whiteSpace: 'nowrap' }}>{healthLabel}</span>
        </div>

        {/* Export Report Action */}
        {onDownloadReport && (
          <button
            onClick={onDownloadReport}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: 'var(--space-2xs) var(--space-sm)',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--color-paper-2)',
              border: 'var(--rule-hair) solid var(--color-rule-2)',
              color: 'var(--color-ink)',
              fontSize: 'var(--text-xs)',
              cursor: 'pointer',
              transition: 'border-color var(--dur-micro) var(--ease-out)'
            }}
            title="Download latest markdown optimization report"
          >
            <Download size={12} />
            <span>Report</span>
          </button>
        )}

        {/* Back to Home / Landing Page */}
        {onNavigateHome && (
          <button
            onClick={onNavigateHome}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: 'var(--space-2xs) var(--space-sm)',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--color-cool-soft)',
              border: 'var(--rule-hair) solid var(--color-rule-2)',
              color: 'var(--color-cool)',
              fontSize: 'var(--text-xs)',
              cursor: 'pointer',
              transition: 'border-color var(--dur-micro) var(--ease-out)'
            }}
            title="Switch to marketing landing page"
          >
            <ExternalLink size={12} />
            <span>Home</span>
          </button>
        )}
      </div>
    </header>
  );
}
