import React from 'react';
import { Terminal, Github, LayoutDashboard, Home, ArrowRight, ExternalLink } from 'lucide-react';

export default function Navbar({ currentPath = '/', onNavigate, status = 'idle' }) {
  const isConsole = currentPath.startsWith('/console');

  return (
    <header className="navbar-container" role="banner">
      <div className="navbar-left">
        <div
          className="navbar-brand"
          onClick={() => onNavigate('/')}
          style={{ cursor: 'pointer' }}
          title="AutoTune 2.0 Home"
        >
          <div className="navbar-logo-icon">
            <Terminal className="w-4 h-4 text-accent" />
          </div>
          <span className="navbar-brand-name">
            AutoTune <span className="brand-badge">2.0</span>
          </span>
        </div>

        <nav className="navbar-links" aria-label="Primary navigation">
          <button
            className={`nav-tab-btn ${!isConsole ? 'active' : ''}`}
            onClick={() => onNavigate('/')}
            type="button"
          >
            <Home className="w-4 h-4" />
            <span>Home</span>
          </button>

          <button
            className={`nav-tab-btn ${isConsole ? 'active' : ''}`}
            onClick={() => onNavigate('/console')}
            type="button"
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Console</span>
            {status === 'running' && (
              <span className="nav-status-dot running" title="Optimization run in progress" />
            )}
          </button>
        </nav>
      </div>

      <div className="navbar-right">
        <div className={`status-pill ${status === 'running' ? 'running' : 'idle'}`}>
          <span className="status-indicator-dot" />
          <span className="status-text">{status === 'running' ? 'Optimization Active' : 'Engine Ready'}</span>
        </div>

        <a
          href="https://github.com/R1shabhCodes/AutoTune"
          target="_blank"
          rel="noopener noreferrer"
          className="navbar-github-btn"
          title="View GitHub Repository"
        >
          <Github className="w-4 h-4" />
          <span>GitHub</span>
        </a>

        {!isConsole ? (
          <button
            className="navbar-cta-btn glow-btn"
            onClick={() => onNavigate('/console')}
            type="button"
          >
            <span>Open Console</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            className="navbar-secondary-btn"
            onClick={() => onNavigate('/')}
            type="button"
          >
            <Home className="w-4 h-4" />
            <span>Product Home</span>
          </button>
        )}
      </div>
    </header>
  );
}
