import React from 'react';
import { Target, Activity, Github, Sparkles, LayoutDashboard, Home } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, status }) {
  return (
    <header className="navbar-container">
      <div className="navbar-left">
        <div className="navbar-brand" onClick={() => setActiveTab('home')}>
          <div className="navbar-logo-icon">
            <Target className="w-5 h-5 text-purple-400" />
          </div>
          <span className="navbar-brand-name">AutoTune <span className="brand-badge">RAG</span></span>
        </div>

        <nav className="navbar-links">
          <button 
            className={`nav-tab-btn ${activeTab === 'home' ? 'active' : ''}`}
            onClick={() => setActiveTab('home')}
          >
            <Home className="w-4 h-4" />
            <span>Home</span>
          </button>

          <button 
            className={`nav-tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Dashboard</span>
            {status === 'running' && (
              <span className="nav-status-dot running" title="Optimizer Running" />
            )}
          </button>
        </nav>
      </div>

      <div className="navbar-right">
        <div className={`status-pill ${status === 'running' ? 'running' : 'idle'}`}>
          <span className="status-indicator-dot" />
          <span className="status-text">{status === 'running' ? 'Optimizing Pipeline...' : 'Engine Idle'}</span>
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

        {activeTab === 'home' ? (
          <button 
            className="navbar-cta-btn glow-btn"
            onClick={() => setActiveTab('dashboard')}
          >
            <Sparkles className="w-4 h-4" />
            <span>Launch Dashboard</span>
          </button>
        ) : (
          <button 
            className="navbar-secondary-btn"
            onClick={() => setActiveTab('home')}
          >
            <span>Overview</span>
          </button>
        )}
      </div>
    </header>
  );
}
