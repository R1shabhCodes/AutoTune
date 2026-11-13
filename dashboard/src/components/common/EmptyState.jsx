import React from 'react';
import { Inbox } from 'lucide-react';

export default function EmptyState({
  title = 'No records found',
  description = 'There are no active records or trials for this view.',
  icon: Icon = Inbox,
  action = null
}) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 'var(--space-xl) var(--space-md)',
      color: 'var(--color-muted)',
      textAlign: 'center'
    }}>
      <Icon size={28} style={{ opacity: 0.5, marginBottom: 'var(--space-xs)', color: 'var(--color-muted)' }} />
      <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--color-ink)' }}>{title}</span>
      <span style={{ fontSize: 'var(--text-xs)', marginTop: 'var(--space-2xs)', maxWidth: '320px', color: 'var(--color-muted)' }}>{description}</span>
      {action && (
        <div style={{ marginTop: 'var(--space-sm)' }}>
          {action}
        </div>
      )}
    </div>
  );
}
