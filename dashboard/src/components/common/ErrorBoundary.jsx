import React from 'react';
import { AlertCircle, RefreshCw, Home } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('AutoTune ErrorBoundary caught an unhandled rendering error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            padding: 'var(--space-xl)',
            background: 'var(--color-paper-2)',
            border: 'var(--rule-hair) solid var(--color-bad)',
            borderRadius: 'var(--radius-card)',
            color: 'var(--color-ink)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-sm)',
            maxWidth: '680px',
            margin: 'var(--space-xl) auto'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
            <AlertCircle size={20} style={{ color: 'var(--color-bad)' }} />
            <h2 style={{ fontSize: 'var(--text-md)', fontWeight: 600, margin: 0, color: 'var(--color-bad)' }}>
              Component Rendering Error
            </h2>
          </div>

          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', margin: 0 }}>
            An unexpected error occurred while rendering this view. AutoTune caught the exception to prevent a complete application unmount.
          </p>

          {this.state.error && (
            <pre
              style={{
                background: 'var(--color-paper-1)',
                padding: 'var(--space-sm)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--text-2xs)',
                fontFamily: 'var(--font-outlier)',
                color: 'var(--color-bad)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                margin: 0,
                border: 'var(--rule-hair) solid var(--color-rule)'
              }}
            >
              {this.state.error.toString()}
            </pre>
          )}

          <div style={{ display: 'flex', gap: 'var(--space-xs)', marginTop: 'var(--space-xs)' }}>
            <button
              type="button"
              onClick={this.handleReset}
              className="console-btn-primary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2xs)' }}
            >
              <RefreshCw size={13} />
              <span>Retry view</span>
            </button>
            <button
              type="button"
              onClick={() => { window.location.href = '/'; }}
              className="console-btn-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2xs)' }}
            >
              <Home size={13} />
              <span>Return to overview</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

