import React, { useState, useEffect, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Play, Activity, Settings, CheckCircle2, XCircle, Info, RefreshCw, Download } from 'lucide-react';

export default function App() {
  const [iterations, setIterations] = useState([]);
  const [status, setStatus] = useState('idle');
  const [bestConfig, setBestConfig] = useState(null);
  const [holdoutScore, setHoldoutScore] = useState(null);
  const [runCount, setRunCount] = useState(15);
  const [errorMsg, setErrorMsg] = useState(null);
  
  const wsRef = useRef(null);

  // Helper to fetch holdout score
  const fetchHoldoutScore = async () => {
    try {
      const res = await fetch('/holdout_score');
      if (res.ok) {
        const data = await res.json();
        setHoldoutScore(data.score);
      }
    } catch (err) {
      console.error('Error fetching holdout score:', err);
    }
  };

  // Helper to fetch history
  const fetchIterations = async () => {
    try {
      const res = await fetch('/iterations');
      if (res.ok) {
        const data = await res.json();
        setIterations(data);
      }
    } catch (err) {
      console.error('Error fetching iterations:', err);
    }
  };

  // Helper to fetch current best config
  const fetchBestConfig = async () => {
    try {
      const res = await fetch('/best');
      if (res.ok) {
        const data = await res.json();
        setBestConfig(data);
        fetchHoldoutScore();
      }
    } catch (err) {
      console.error('Error fetching best config:', err);
    }
  };

  // Establish WebSocket connection
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    // Handle dev vs prod ports
    const wsUrl = wsHost.includes('5173')
      ? 'ws://localhost:8000/ws'
      : `${protocol}//${wsHost}/ws`;

    console.log('Connecting to WebSocket at:', wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'status') {
          setStatus(msg.data);
        } else if (msg.type === 'iteration') {
          const iterData = msg.data;
          
          // Prepend new iteration (newest first)
          setIterations((prev) => {
            // Check if already exists to prevent duplicate renders
            if (prev.some(item => item.iteration_number === iterData.iteration_number)) {
              return prev;
            }
            return [iterData, ...prev];
          });
          
          // Refresh best config if accepted
          if (iterData.accepted) {
            fetchBestConfig();
          }
        }
      } catch (err) {
        console.error('Error processing websocket message:', err);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected. Reconnecting in 3s...');
      setTimeout(() => {
        // Simple reconnect logic if component is still mounted
        if (wsRef.current === ws) {
          setStatus('idle');
        }
      }, 3000);
    };

    // Load initial data
    fetchIterations();
    fetchBestConfig();
    fetchHoldoutScore();

    return () => {
      ws.close();
    };
  }, []);

  // Run the optimizer
  const handleStartRun = async () => {
    setErrorMsg(null);
    try {
      const res = await fetch('/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ iterations: runCount })
      });
      const data = await res.json();
      if (data.status === 'error') {
        setErrorMsg(data.message);
      } else {
        setStatus('running');
      }
    } catch (err) {
      setErrorMsg('Failed to trigger the optimization run. Is the server online?');
    }
  };

  // Process data for Recharts (requires oldest first)
  const chartData = [...iterations]
    .sort((a, b) => a.iteration_number - b.iteration_number)
    .map((item) => ({
      iteration: item.iteration_number,
      score: parseFloat(item.new_score.toFixed(4)),
      param: item.param,
      accepted: item.accepted
    }));

  // Custom tool tip for chart
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div style={{
          background: 'rgba(10, 12, 22, 0.9)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          padding: '0.75rem',
          borderRadius: '8px',
          color: '#f3f4f6',
          fontSize: '0.85rem'
        }}>
          <p style={{ fontWeight: 600 }}>Iteration {data.iteration}</p>
          <p style={{ color: '#10b981' }}>Score: {data.score}</p>
          {data.param !== 'None' && (
            <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
              Tuned: <span style={{ color: '#06b6d4', fontFamily: 'monospace' }}>{data.param}</span>
            </p>
          )}
          <p style={{
            fontSize: '0.75rem',
            color: data.accepted ? '#10b981' : '#ef4444',
            fontWeight: 500,
            marginTop: '0.15rem'
          }}>
            {data.accepted ? 'Accepted ✓' : 'Rejected ✗'}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="header-title-section">
          <span className="logo-icon">🎯</span>
          <div>
            <h1>AutoTune RAG</h1>
            <p>Self-improving retrieval-augmented generation pipeline optimizer</p>
          </div>
        </div>
        
        {/* Run Controls */}
        <div className="status-container">
          <div className={`status-dot ${status}`}></div>
          <span className={`status-text ${status}`}>{status}</span>
        </div>
      </header>

      {/* Top Cards Grid */}
      <div className="top-grid">
        {/* Controls Card */}
        <div className="glass-card controls-section">
          <h2 className="section-title"><Settings size={16} /> Controller</h2>
          <div className="input-group">
            <input 
              type="number" 
              className="number-input"
              value={runCount} 
              onChange={(e) => setRunCount(Math.max(1, parseInt(e.target.value) || 1))}
              disabled={status === 'running'}
              min="1"
              max="50"
            />
            <button 
              className="btn-primary"
              onClick={handleStartRun}
              disabled={status === 'running'}
            >
              {status === 'running' ? (
                <>
                  <RefreshCw className="animate-spin" size={16} /> Tuning...
                </>
              ) : (
                <>
                  <Play size={16} /> Start Run
                </>
              )}
            </button>
            <button 
              className="btn-secondary"
              onClick={() => { window.location.href = '/report/current'; }}
              disabled={status === 'running' || iterations.length === 0}
              title="Download Markdown Report"
            >
              <Download size={16} /> Report
            </button>
          </div>
          {errorMsg && <p style={{ color: '#ef4444', fontSize: '0.8rem', marginTop: '0.25rem' }}>{errorMsg}</p>}
        </div>

        {/* Best Config Card */}
        <div className="glass-card">
          <h2 className="section-title"><Activity size={16} /> Current Best Config</h2>
          {bestConfig ? (
            <div className="best-config-content">
              <div className="score-split-container" style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.75rem' }}>
                <div className="best-score-display" style={{ flex: 1 }}>
                  <span className="best-score-val" style={{ fontSize: '1.8rem' }}>{bestConfig.score.toFixed(4)}</span>
                  <span className="best-score-label" style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Tuning Score</span>
                </div>
                <div className="best-score-display" style={{ flex: 1, borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '1.5rem' }}>
                  <span className="best-score-val" style={{ fontSize: '1.8rem', color: '#06b6d4' }}>
                    {holdoutScore !== null ? holdoutScore.toFixed(4) : '---'}
                  </span>
                  <span className="best-score-label" style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Holdout Score</span>
                </div>
              </div>
              <div className="config-grid">
                <div className="config-item">
                  <div className="config-label">chunk_size</div>
                  <div className="config-val">{bestConfig.config.chunk_size}</div>
                </div>
                <div className="config-item">
                  <div className="config-label">overlap</div>
                  <div className="config-val">{bestConfig.config.chunk_overlap}</div>
                </div>
                <div className="config-item">
                  <div className="config-label">top_k</div>
                  <div className="config-val">{bestConfig.config.top_k}</div>
                </div>
                <div className="config-item">
                  <div className="config-label">temp</div>
                  <div className="config-val">{bestConfig.config.temperature}</div>
                </div>
              </div>
              <div className="prompt-template-preview" title="Current prompt template">
                {bestConfig.config.prompt_template}
              </div>
            </div>
          ) : (
            <div className="empty-feed" style={{ padding: '0.5rem 0' }}>
              <p style={{ fontSize: '0.85rem' }}>No evaluation completed yet.</p>
            </div>
          )}
        </div>

        {/* LLM Engine Info Card */}
        <div className="glass-card api-info-panel">
          <h2 className="section-title"><Info size={16} /> LLM Provider</h2>
          <div className="api-badge">
            <Activity size={12} /> Auto-Detect Mode
          </div>
          <p className="api-desc">
            Uses <strong>Gemini API</strong> (gemini-1.5-flash) if <code>GEMINI_API_KEY</code> is loaded, otherwise falls back to a local <strong>Ollama</strong> instance (llama3.2).
          </p>
        </div>
      </div>

      {/* Main Sections Grid */}
      <div className="dashboard-grid">
        {/* Left Column: Progress Chart */}
        <div className="glass-card column-card chart-card">
          <h2 className="section-title">Optimization Progress</h2>
          {chartData.length > 0 ? (
            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis 
                    dataKey="iteration" 
                    stroke="var(--text-secondary)" 
                    tickLine={false}
                    fontSize={12}
                  />
                  <YAxis 
                    stroke="var(--text-secondary)" 
                    domain={[0.0, 1.0]} 
                    tickLine={false}
                    fontSize={12}
                    tickFormatter={(val) => val.toFixed(1)}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Line 
                    type="monotone" 
                    dataKey="score" 
                    stroke="var(--accent-purple)" 
                    strokeWidth={3}
                    dot={(props) => {
                      const { cx, cy, payload } = props;
                      if (payload.iteration === 0) return null; // hide baseline dot if desired
                      return (
                        <circle 
                          key={payload.iteration}
                          cx={cx} 
                          cy={cy} 
                          r={4} 
                          fill={payload.accepted ? 'var(--status-green)' : 'var(--status-red)'}
                          stroke="none"
                        />
                      );
                    }}
                    activeDot={{ r: 6, strokeWidth: 0 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-feed">
              <span className="empty-icon">📈</span>
              <p>Waiting for run to start...</p>
            </div>
          )}
        </div>

        {/* Right Column: Iteration Feed */}
        <div className="glass-card column-card">
          <h2 className="section-title">Iteration Log</h2>
          <div className="feed-wrapper">
            {iterations.length > 0 ? (
              iterations.map((item) => (
                <div 
                  key={item.iteration_number} 
                  className={`feed-item ${item.accepted ? 'accepted' : 'rejected'}`}
                >
                  <div className="feed-item-header">
                    <span className="feed-item-title">
                      Iteration #{item.iteration_number}
                      <span className={`badge ${item.accepted ? 'accepted' : 'rejected'}`}>
                        {item.accepted ? 'Accepted' : 'Rejected'}
                      </span>
                    </span>
                    <span className="feed-timestamp">{item.timestamp}</span>
                  </div>

                  {item.hypothesis && item.iteration_number > 0 && (
                    <p className="feed-hypothesis">
                      &ldquo;{item.hypothesis}&rdquo;
                    </p>
                  )}

                  {item.motivated_by && item.iteration_number > 0 && (
                    <div className="feed-motivated-by" style={{ margin: '0.2rem 0 0.5rem 0', fontSize: '0.72rem', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.05)', border: '1px solid rgba(56, 189, 248, 0.15)', padding: '0.15rem 0.4rem', borderRadius: '4px', display: 'inline-block', lineHeight: '1.2' }}>
                      <span style={{ fontWeight: 600 }}>Targeting:</span> {item.motivated_by.split(' | ').join(', ')}
                    </div>
                  )}

                  <div className="feed-change-grid">
                    <div className="param-diff">
                      {item.iteration_number === 0 ? (
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Baseline Setup</span>
                      ) : (
                        <>
                          <span className="param-name">{item.param}</span>:
                          <span className="diff-old">{item.old_value}</span>
                          <span>&rarr;</span>
                          <span className="diff-new">{item.new_value}</span>
                        </>
                      )}
                    </div>
                    
                    <div className={`score-progress ${item.accepted ? 'improved' : ''}`}>
                      {item.iteration_number === 0 ? (
                        <span>Score: {item.new_score.toFixed(4)}</span>
                      ) : (
                        <>
                          <span>{item.old_score.toFixed(3)}</span>
                          <span>&rarr;</span>
                          <span>{item.new_score.toFixed(3)}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-feed">
                <span className="empty-icon">📋</span>
                <p>No iterations logged yet.</p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Click "Start Run" to begin optimization.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
