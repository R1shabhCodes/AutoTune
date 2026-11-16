import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorState({ error, onRetry }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '2rem 1rem',
        borderRadius: 'var(--radius-card)',
        background: 'var(--color-bad-soft)',
        border: 'var(--rule-hair) solid var(--color-bad)',
        color: 'var(--color-bad)',
        textAlign: 'center'
      }}
    >
      <AlertCircle size={24} style={{ marginBottom: '0.5rem', color: 'var(--color-bad)' }} />
      <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--color-ink)' }}>{error || 'Failed to communicate with AutoTune backend'}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginTop: '0.75rem',
            padding: 'var(--space-2xs) var(--space-sm)',
            borderRadius: 'var(--radius-pill)',
            background: 'var(--color-paper-2)',
            border: 'var(--rule-hair) solid var(--color-rule-2)',
            color: 'var(--color-ink)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontSize: 'var(--text-xs)',
            transition: 'border-color var(--dur-micro) var(--ease-out)'
          }}
        >
          <RefreshCw size={13} /> Retry
        </button>
      )}
    </div>
  );
}

