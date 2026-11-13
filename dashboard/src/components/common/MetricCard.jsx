import React from 'react';

export default function MetricCard({ title, value, subtitle, icon: Icon, color = 'var(--color-ink)', badge }) {
  return (
    <div
      style={{
        background: 'var(--color-paper-2)',
        border: 'var(--rule-hair) solid var(--color-rule)',
        borderRadius: 'var(--radius-card)',
        padding: 'var(--space-md)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        position: 'relative',
        minHeight: '100px'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', fontWeight: 500 }}>
          {title}
        </span>
        {Icon && <Icon size={16} style={{ color: color, opacity: 0.85 }} />}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
        <span style={{ fontSize: 'var(--text-display)', fontWeight: 500, color: color, fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums slashed-zero' }}>
          {value !== null && value !== undefined ? value : '---'}
        </span>
        {badge}
      </div>
      {subtitle && (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginTop: '0.25rem' }}>
          {subtitle}
        </span>
      )}
    </div>
  );
}

