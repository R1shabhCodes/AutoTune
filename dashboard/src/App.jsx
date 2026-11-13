import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  CheckCircle2, Sparkles, ShieldCheck, Sliders, Server, Cpu, Terminal
} from 'lucide-react';
import Navbar from './components/Navbar';
import LandingPage from './components/LandingPage';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import OverviewView from './views/OverviewView';
import TrialWorkspaceView from './views/TrialWorkspaceView';
import LiveMonitor from './components/monitor/LiveMonitor';
import ExperimentWizard from './components/experiment/ExperimentWizard';
import ApplicationsView from './views/ApplicationsView';
import PromotionsView from './views/PromotionsView';
import EvaluationAnalyticsView from './views/EvaluationAnalyticsView';
import StatusBadge from './components/common/StatusBadge';
import MetricCard from './components/common/MetricCard';
import ErrorBoundary from './components/common/ErrorBoundary';
import { api } from './api/client';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard'); // 'dashboard' or 'home'
  const [activePage, setActivePage] = useState('overview'); // sidebar navigation
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Core Data States
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  const [iterations, setIterations] = useState([]);
  const [bestConfig, setBestConfig] = useState(null);
  const [holdoutScore, setHoldoutScore] = useState(null);
  const [adapters, setAdapters] = useState([]);
  const [status, setStatus] = useState('idle');
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);

  // WebSocket Resiliency & Live Telemetry States
  const [wsStatus, setWsStatus] = useState('connecting'); // 'connected' | 'disconnected' | 'connecting' | 'reconnecting'
  const [lastEventTime, setLastEventTime] = useState(null);
  const [activeExperimentId, setActiveExperimentId] = useState(null);

  // Trials / Experiment Controls
  const [runCount, setRunCount] = useState(15);
  const [isWizardOpen, setIsWizardOpen] = useState(false);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const isUnmountedRef = useRef(false);
  const reconnectDelayRef = useRef(1000);

  // Fetch all initial data
  const fetchAllData = async () => {
    try {
      const [healthData, summaryData, itersData, bestData, holdoutData, adaptersData] = await Promise.allSettled([
        api.getHealth(),
        api.getOverviewSummary(),
        api.getIterations(),
        api.getBestConfig(),
        api.getHoldoutScore(),
        api.getAdapters()
      ]);

      if (healthData.status === 'fulfilled') setHealth(healthData.value);
      if (summaryData.status === 'fulfilled') setSummary(summaryData.value);
      if (itersData.status === 'fulfilled') setIterations(itersData.value);
      if (bestData.status === 'fulfilled') setBestConfig(bestData.value);
      if (holdoutData.status === 'fulfilled') setHoldoutScore(holdoutData.value.score);
      if (adaptersData.status === 'fulfilled') {
        const val = adaptersData.value;
        const adList = Array.isArray(val)
          ? val
          : Array.isArray(val?.adapters)
            ? val.adapters
            : Object.entries(val || {}).map(([id, meta]) => ({
              adapter_id: id,
              name: meta.application || id,
              ...meta
            }));
        setAdapters(adList);
      }
    } catch (err) {
      console.error('Error fetching initial data:', err);
      setErrorMsg('Failed to fetch platform telemetry from AutoTune backend.');
    } finally {
      setLoading(false);
    }
  };

  // Re-fetch overview and health
  const refreshTelemetry = async () => {
    try {
      const [h, s] = await Promise.all([api.getHealth(), api.getOverviewSummary()]);
      setHealth(h);
      setSummary(s);
    } catch (e) {
      console.error('Error refreshing telemetry:', e);
    }
  };

  // Resilient WebSocket Connection Manager with Reconnection & Heartbeat
  const connectWs = useCallback(() => {
    if (isUnmountedRef.current) return;

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const wsUrl = api.getWebSocketUrl();
    console.log('Connecting to AutoTune WebSocket at:', wsUrl);
    setWsStatus('connecting');

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isUnmountedRef.current) return;
        console.log('WebSocket connected successfully.');
        setWsStatus('connected');
        reconnectDelayRef.current = 1000; // Reset exponential backoff

        // Setup periodic heartbeat ping to prevent proxy/socket timeouts
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            try {
              ws.send('ping');
            } catch (_) { }
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        if (isUnmountedRef.current) return;
        setWsStatus('connected');
        setLastEventTime(new Date().toLocaleTimeString());

        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'status') {
            setStatus(msg.data);
            if (msg.data === 'idle') {
              fetchAllData();
            }
          } else if (msg.type === 'iteration') {
            const iterData = msg.data;
            if (iterData.experiment_id) {
              setActiveExperimentId(iterData.experiment_id);
            }

            setIterations((prev) => {
              if (prev.some(item => item.iteration_number === iterData.iteration_number)) {
                return prev;
              }
              return [iterData, ...prev];
            });

            refreshTelemetry();

            if (iterData.accepted) {
              api.getBestConfig().then(setBestConfig).catch(console.error);
              api.getHoldoutScore().then(d => setHoldoutScore(d.score)).catch(console.error);
            }
          } else if (msg.type === 'error') {
            console.error('Optimization error received from backend:', msg.data);
            setErrorMsg(typeof msg.data === 'string' ? msg.data : 'Optimization task error');
          }
        } catch (err) {
          console.error('Error processing websocket message:', err);
        }
      };

      ws.onclose = (event) => {
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        if (isUnmountedRef.current) return;

        console.log('WebSocket closed. Scheduling reconnection in', reconnectDelayRef.current, 'ms');
        setWsStatus('reconnecting');

        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(10000, reconnectDelayRef.current * 1.5);
          connectWs();
        }, reconnectDelayRef.current);
      };

      ws.onerror = (err) => {
        console.error('WebSocket connection error:', err);
        // onclose will automatically fire and handle reconnection
      };
    } catch (e) {
      console.error('Failed to instantiate WebSocket:', e);
      setWsStatus('disconnected');
    }
  }, []);

  // Mount WebSocket and initial data fetch
  useEffect(() => {
    isUnmountedRef.current = false;
    fetchAllData();
    connectWs();

    return () => {
      isUnmountedRef.current = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (_) { }
      }
    };
  }, [connectWs]);

  // Run the optimizer (supports both quick-run and comprehensive wizard payload)
  const handleStartRun = async (customPayload = null) => {
    setErrorMsg(null);
    try {
      const payload = customPayload || { iterations: runCount };
      if (payload.experiment_id) {
        setActiveExperimentId(payload.experiment_id);
      }
      if (payload.iterations) {
        setRunCount(payload.iterations);
      }

      const data = await api.startRun(payload);
      if (data.status === 'error') {
        setErrorMsg(data.message);
        throw new Error(data.message);
      } else {
        setStatus('running');
      }
    } catch (err) {
      const msg = err.message || 'Failed to trigger optimization run. Is backend online?';
      setErrorMsg(msg);
      throw err;
    }
  };

  // Active target app name
  const activeAppName = adapters.length > 0
    ? (adapters[0].name || adapters[0].adapter_id)
    : 'Finance RAG (Internal)';

  // If user navigated to Home (marketing page), preserve LandingPage view
  if (activeTab === 'home') {
    return (
      <div className="app-root mode-landing">
        <Navbar activeTab={activeTab} setActiveTab={setActiveTab} status={status} />
        <LandingPage setActiveTab={setActiveTab} />
      </div>
    );
  }

  // Developer Workspace
  return (
    <div className="dev-workspace">
      {/* Universal Sidebar */}
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      />

      <div className="dev-main">
        {/* Universal Top Header */}
        <Header
          health={health}
          activeApp={activeAppName}
          activePage={activePage}
          onDownloadReport={() => { window.location.href = '/report/current'; }}
          wsStatus={wsStatus}
          runStatus={status}
          onNavigateHome={() => setActiveTab('home')}
          onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          isSidebarCollapsed={isSidebarCollapsed}
        />

        {/* Dynamic Page Content */}
        <div className="dev-content-scroll">
          <ErrorBoundary key={activePage} onReset={() => setActivePage('overview')}>
          {activePage === 'overview' && (
            <OverviewView
              summary={summary}
              health={health}
              iterations={iterations}
              loading={loading}
              error={errorMsg}
              onRefresh={fetchAllData}
              onNavigate={(page) => setActivePage(page)}
            />
          )}

          {activePage === 'experiments' && (
            <LiveMonitor
              status={status}
              wsStatus={wsStatus}
              lastEventTime={lastEventTime}
              activeExperimentId={activeExperimentId}
              trialBudget={runCount}
              iterations={iterations}
              bestConfig={bestConfig}
              holdoutScore={holdoutScore}
              errorMsg={errorMsg}
              onOpenWizard={() => setIsWizardOpen(true)}
              activeAppName={activeAppName}
            />
          )}

          {activePage === 'trials' && (
            <TrialWorkspaceView
              iterations={iterations}
              bestConfig={bestConfig}
              holdoutScore={holdoutScore}
              status={status}
              runCount={runCount}
              setRunCount={setRunCount}
              onStartRun={handleStartRun}
              errorMsg={errorMsg}
              onDownloadReport={() => { window.location.href = '/report/current'; }}
              adapters={adapters}
            />
          )}

          {activePage === 'applications' && (
            <ApplicationsView
              adapters={adapters}
              onRefresh={fetchAllData}
            />
          )}

          {activePage === 'evaluations' && (
            <EvaluationAnalyticsView
              iterations={iterations}
              holdoutScore={holdoutScore}
              bestConfig={bestConfig}
              onDownloadReport={() => { window.location.href = '/report/current'; }}
            />
          )}

          {activePage === 'optimization' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
              <div>
                <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-ink)', margin: 0 }}>
                  Hybrid Optimization Architecture
                </h1>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', margin: 'var(--space-2xs) 0 0 0' }}>
                  Optuna TPE Bayesian exploration coupled with Qwen 2.5 LLM diagnostic hypotheses.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-sm)' }}>
                <MetricCard title="Bayesian Engine" value="Optuna TPE" subtitle="SQLite persistent study" icon={Sliders} color="var(--color-accent)" />
                <MetricCard title="Diagnostician" value="Qwen 2.5 1.5B" subtitle="Ollama local LLM reasoning" icon={Cpu} color="var(--color-cool)" />
                <MetricCard title="Generator" value="Llama 3.2 3B" subtitle="Target RAG response generator" icon={Terminal} color="var(--color-cool)" />
              </div>
            </div>
          )}

          {activePage === 'promotions' && (
            <PromotionsView
              bestConfig={bestConfig}
              holdoutScore={holdoutScore}
              adapters={adapters}
              onRefresh={fetchAllData}
            />
          )}

          {activePage === 'settings' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
              <div>
                <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-ink)', margin: 0 }}>
                  System Settings & Connectivity
                </h1>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', margin: 'var(--space-2xs) 0 0 0' }}>
                  Configured model providers, Ollama endpoints, and backend telemetry parameters.
                </p>
              </div>

              <div className="console-panel" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2xs) 0', borderBottom: 'var(--rule-hair) solid var(--color-rule)' }}>
                  <span style={{ color: 'var(--color-muted)', fontSize: 'var(--text-xs)' }}>Inference provider:</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                    <span style={{ fontFamily: 'var(--font-outlier)', color: 'var(--color-ink)', fontSize: 'var(--text-xs)' }}>
                      {health?.inference_url || 'Configured endpoint (http://localhost:11434)'}
                    </span>
                    <StatusBadge
                      status={health?.ollama_available ? 'healthy' : 'degraded'}
                      label={health?.ollama_available ? 'Connected' : 'Unreachable'}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2xs) 0', borderBottom: 'var(--rule-hair) solid var(--color-rule)' }}>
                  <span style={{ color: 'var(--color-muted)', fontSize: 'var(--text-xs)' }}>Optimization engine:</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                    <span style={{ fontFamily: 'var(--font-outlier)', color: 'var(--color-accent)', fontSize: 'var(--text-xs)' }}>
                      {health?.optimizer?.model || (typeof health?.optimizer === 'string' ? health.optimizer : 'qwen2.5:1.5b')}
                    </span>
                    <StatusBadge
                      status={health?.optimizer?.ready ? 'healthy' : 'degraded'}
                      label={health?.optimizer?.ready ? 'Ready' : 'Not Loaded'}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2xs) 0', borderBottom: 'var(--rule-hair) solid var(--color-rule)' }}>
                  <span style={{ color: 'var(--color-muted)', fontSize: 'var(--text-xs)' }}>Response generation engine:</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                    <span style={{ fontFamily: 'var(--font-outlier)', color: 'var(--color-cool)', fontSize: 'var(--text-xs)' }}>
                      {health?.generator?.model || (typeof health?.generator === 'string' ? health.generator : 'llama3.2:3b')}
                    </span>
                    <StatusBadge
                      status={health?.generator?.ready ? 'healthy' : 'degraded'}
                      label={health?.generator?.ready ? 'Ready' : 'Not Loaded'}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2xs) 0' }}>
                  <span style={{ color: 'var(--color-muted)', fontSize: 'var(--text-xs)' }}>Backend service:</span>
                  <StatusBadge status={health?.status === 'healthy' ? 'healthy' : (health?.status === 'degraded' ? 'degraded' : 'unhealthy')} label={health?.status || 'Unknown'} />
                </div>
              </div>
            </div>
          )}
          </ErrorBoundary>
        </div>
      </div>

      {/* Experiment Configuration Wizard Modal */}
      <ExperimentWizard
        isOpen={isWizardOpen}
        onClose={() => setIsWizardOpen(false)}
        onLaunch={handleStartRun}
        adapters={adapters}
        isSystemRunning={status === 'running'}
      />
    </div>
  );
}
