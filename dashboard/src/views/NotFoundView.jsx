import React from 'react';
import { Compass, Home, LayoutDashboard, ArrowLeft } from 'lucide-react';

export default function NotFoundView({ onNavigate }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '70vh',
        padding: 'var(--space-2xl) var(--space-md)',
        textAlign: 'center',
        background: 'var(--color-paper)',
        color: 'var(--color-ink)'
      }}
    >
      <div
        style={{
          width: '64px',
          height: '64px',
          borderRadius: '50%',
          background: 'var(--color-paper-2)',
          border: 'var(--rule-hair) solid var(--color-rule-2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 'var(--space-md)',
          color: 'var(--color-accent)'
        }}
      >
        <Compass size={32} />
      </div>

      <div
        style={{
          fontSize: 'var(--text-xs)',
          fontFamily: 'var(--font-outlier)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          color: 'var(--color-accent)',
          marginBottom: 'var(--space-2xs)'
        }}
      >
        404 · Route Not Found
      </div>

      <h1
        style={{
          fontSize: 'var(--text-2xl)',
          fontWeight: 600,
          color: 'var(--color-ink)',
          marginBottom: 'var(--space-xs)'
        }}
      >
        Page Does Not Exist
      </h1>

      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--color-muted)',
          maxWidth: '460px',
          lineHeight: 1.6,
          marginBottom: 'var(--space-xl)'
        }}
      >
        The requested URL was not found in AutoTune. Please verify the address or navigate back to the product home or application console.
      </p>

      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', justifyContent: 'center' }}>
        <button
          onClick={() => onNavigate('/')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-xs)',
            padding: 'var(--space-xs) var(--space-lg)',
            borderRadius: 'var(--radius-pill)',
            background: 'var(--color-paper-2)',
            border: 'var(--rule-hair) solid var(--color-rule-2)',
            color: 'var(--color-ink)',
            fontSize: 'var(--text-sm)',
            cursor: 'pointer'
          }}
        >
          <Home size={16} />
          <span>Return Home</span>
        </button>

        <button
          onClick={() => onNavigate('/console')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-xs)',
            padding: 'var(--space-xs) var(--space-lg)',
            borderRadius: 'var(--radius-pill)',
            background: 'var(--color-accent)',
            border: 'none',
            color: 'var(--color-accent-ink)',
            fontSize: 'var(--text-sm)',
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >
          <LayoutDashboard size={16} />
          <span>Open Console</span>
        </button>
      </div>
    </div>
  );
}

