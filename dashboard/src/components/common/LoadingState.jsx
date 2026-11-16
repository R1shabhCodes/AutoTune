import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingState({ message = 'Loading live telemetry...' }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3rem 1rem', color: 'var(--color-muted)' }}>
      <Loader2 className="animate-spin" size={24} style={{ color: 'var(--color-cool)', marginBottom: '0.75rem' }} />
      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>{message}</span>
    </div>
  );
}

