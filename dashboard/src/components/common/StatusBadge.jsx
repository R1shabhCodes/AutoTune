import React from 'react';

export default function StatusBadge({ status, label }) {
  const s = (status || '').toLowerCase();

  let bg = 'var(--color-paper-3)';
  let color = 'var(--color-muted)';
  let border = 'var(--color-rule)';

  if (s === 'accepted' || s === 'healthy' || s === 'online' || s === 'success' || s === 'approved') {
    bg = 'var(--color-ok-soft)';
    color = 'var(--color-ok)';
    border = 'var(--color-rule-2)';
  } else if (s === 'rejected' || s === 'unhealthy' || s === 'error' || s === 'failed') {
    bg = 'var(--color-bad-soft)';
    color = 'var(--color-bad)';
    border = 'var(--color-rule-2)';
  } else if (s === 'baseline' || s === 'instrument') {
    bg = 'var(--color-cool-soft)';
    color = 'var(--color-cool)';
    border = 'var(--color-rule-2)';
  } else if (s === 'degraded' || s === 'observe' || s === 'running' || s === 'operator') {
    bg = 'var(--color-accent-soft)';
    color = 'var(--color-accent)';
    border = 'var(--color-rule-2)';
  } else if (s === 'optimize') {
    bg = 'var(--color-cool-soft)';
    color = 'var(--color-cool)';
    border = 'var(--color-rule-2)';
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: 'var(--radius-pill)',
        fontSize: 'var(--text-xs)',
        fontWeight: 500,
        backgroundColor: bg,
        color: color,
        border: `var(--rule-hair) solid ${border}`,
        whiteSpace: 'nowrap'
      }}
    >
      {label || status || 'Unknown'}
    </span>
  );
}

