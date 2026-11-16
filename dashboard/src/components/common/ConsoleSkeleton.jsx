import React from 'react';

export default function ConsoleSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)', padding: 'var(--space-md)' }}>
      {/* Top metrics skeleton row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-sm)' }}>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            style={{
              height: '84px',
              borderRadius: 'var(--radius-card)',
              background: 'var(--color-paper-2)',
              border: 'var(--rule-hair) solid var(--color-rule)',
              padding: 'var(--space-sm)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div style={{ width: '40%', height: '12px', background: 'var(--color-rule)', borderRadius: '4px' }} />
            <div style={{ width: '60%', height: '24px', background: 'var(--color-rule-2)', borderRadius: '4px' }} />
          </div>
        ))}
      </div>

      {/* Main card skeleton */}
      <div
        style={{
          height: '280px',
          borderRadius: 'var(--radius-card)',
          background: 'var(--color-paper-2)',
          border: 'var(--rule-hair) solid var(--color-rule)',
          padding: 'var(--space-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-sm)'
        }}
      >
        <div style={{ width: '30%', height: '16px', background: 'var(--color-rule)', borderRadius: '4px' }} />
        <div style={{ width: '100%', flex: 1, background: 'rgba(255, 255, 255, 0.02)', borderRadius: '6px', border: '1px dashed var(--color-rule)' }} />
      </div>

      {/* Table skeleton */}
      <div
        style={{
          height: '180px',
          borderRadius: 'var(--radius-card)',
          background: 'var(--color-paper-2)',
          border: 'var(--rule-hair) solid var(--color-rule)',
          padding: 'var(--space-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-xs)'
        }}
      >
        <div style={{ width: '25%', height: '14px', background: 'var(--color-rule)', borderRadius: '4px', marginBottom: '8px' }} />
        <div style={{ width: '100%', height: '24px', background: 'var(--color-rule-2)', borderRadius: '4px' }} />
        <div style={{ width: '100%', height: '24px', background: 'var(--color-rule)', borderRadius: '4px' }} />
        <div style={{ width: '100%', height: '24px', background: 'var(--color-rule-2)', borderRadius: '4px' }} />
      </div>
    </div>
  );
}

