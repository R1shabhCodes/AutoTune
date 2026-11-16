import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  CheckCircle2, Sparkles, ShieldCheck, Sliders, Server, Cpu, Terminal
} from 'lucide-react';
import Navbar from './components/Navbar';
import LandingPage from './components/LandingPage';
import NotFoundView from './views/NotFoundView';
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
import ConsoleSkeleton from './components/common/ConsoleSkeleton';
import { api } from './api/client';

const VALID_CONSOLE_PAGES = [
  'overview',
  'applications',
  'evaluations',
  'experiments',
  'trials',
  'optimization',
  'promotions',
  'settings'
];

const PAGE_ALIASES = {
  '': 'overview',
  'diff': 'promotions',
  'history': 'trials',
  'monitor': 'experiments'
};

function parseRoute(pathname) {
  const clean = pathname ? pathname.replace(/\/+$/, '') : '';
  if (clean === '' || clean === '/') {
    return { view: 'home', page: 'overview' };
  }

  if (clean === '/console' || clean.startsWith('/console/')) {
    const rawSub = clean.replace(/^\/console\/?/, '').split('/')[0] || 'overview';
    const resolvedPage = PAGE_ALIASES[rawSub] || rawSub;
    if (VALID_CONSOLE_PAGES.includes(resolvedPage)) {
      return { view: 'console', page: resolvedPage };
    }
    return { view: 'not-found', page: '404' };
  }

  return { view: 'not-found', page: '404' };
}

export default function App() {
  const [route, setRoute] = useState(() => parseRoute(window.location.pathname));
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Core Data States
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  const [iterations, setIterations] = useState([]);
  const [bestConfig, setBestConfig] = useState(null);
  const [holdoutScore, setHoldoutScore] = useState(null);
  const [adapters, setAdapters] = useState([]);
  const [status, setStatus] = useState('idle');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // WebSocket Resiliency & Live Telemetry States
  const [wsStatus, setWsStatus] = useState('disconnected');
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
  const hasLoadedConsoleDataRef = useRef(false);

  // Synchronize browser history and route state
  const navigate = useCallback((toPath) => {
    if (window.location.pathname !== toPath) {
      window.history.pushState({}, '', toPath);
    }
    setRoute(parseRoute(toPath));
    window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setRoute(parseRoute(window.location.pathname));
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Preload telemetry during idle time when on Home page
  useEffect(() => {
    if (route.view === 'home') {
      const schedulePreload = window.requestIdleCallback || ((cb) => setTimeout(cb, 1000));
      const cancelPreload = window.cancelIdleCallback || clearTimeout;
      const handle = schedulePreload(() => {
        api.preloadTelemetry();
      });
      return () => cancelPreload(handle);
    }
  }, [route.view]);

  // Fetch console data with progressive loading and error isolation
  const fetchConsoleData = useCallback(async (force = false) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [healthRes, summaryRes, itersRes, bestRes, adaptersRes] = await Promise.allSettled([
        api.getHealth({ forceRefresh: force }),
        api.getOverviewSummary({ forceRefresh: force }),
        api.getIterations(null, { forceRefresh: force }),
        api.getBestConfig(null, { forceRefresh: force }),
        api.getAdapters({ forceRefresh: force })
      ]);

      if (healthRes.status === 'fulfilled') setHealth(healthRes.value);
      if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value);
      if (itersRes.status === 'fulfilled') setIterations(itersRes.value || []);
      if (bestRes.status === 'fulfilled') setBestConfig(bestRes.value);
      if (adaptersRes.status === 'fulfilled') {
        const val = adaptersRes.value;
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
      hasLoadedConsoleDataRef.current = true;
    } catch (err) {
      console.error('Error fetching console data:', err);
      setErrorMsg('Failed to load platform telemetry from AutoTune backend.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Re-fetch overview and health on demand
  const refreshTelemetry = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([
        api.getHealth({ forceRefresh: true }),
        api.getOverviewSummary({ forceRefresh: true })
      ]);
      setHealth(h);
      setSummary(s);
    } catch (e) {
      console.error('Error refreshing telemetry:', e);
    }
  }, []);

  // Resilient WebSocket Connection Manager (Active strictly when in console)
  const connectWs = useCallback(() => {
    if (isUnmountedRef.current || route.view !== 'console') return;

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const wsUrl = api.getWebSocketUrl();
    setWsStatus('connecting');

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isUnmountedRef.current) return;
        setWsStatus('connected');
        reconnectDelayRef.current = 1000;

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
              fetchConsoleData(true);
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
            }
          } else if (msg.type === 'error') {
            setErrorMsg(typeof msg.data === 'string' ? msg.data : 'Optimization task error');
          }
        } catch (err) {
          console.error('Error processing websocket message:', err);
        }
      };

      ws.onclose = () => {
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        if (isUnmountedRef.current || route.view !== 'console') return;

        setWsStatus('reconnecting');
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(10000, reconnectDelayRef.current * 1.5);
          connectWs();
        }, reconnectDelayRef.current);
      };

      ws.onerror = () => {
        // onclose will handle reconnection
      };
    } catch (e) {
      setWsStatus('disconnected');
    }
  }, [route.view, fetchConsoleData, refreshTelemetry]);

  // Manage Console Lifecycle: Load data and open WebSocket only when entering console
  useEffect(() => {
    isUnmountedRef.current = false;

    if (route.view === 'console') {
      if (!hasLoadedConsoleDataRef.current) {
        fetchConsoleData();
      }
      connectWs();
    } else {
      // Disconnect WebSocket when leaving console to conserve resources
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (_) { }
        wsRef.current = null;
      }
      setWsStatus('disconnected');
    }

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
  }, [route.view, connectWs, fetchConsoleData]);

  // Run the optimizer
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

  // ROUTE 1: PUBLIC HOME / LANDING PAGE (Default entry point)
  if (route.view === 'home') {
    return (
      <div className="app-root mode-landing">
        <Navbar currentPath="/" onNavigate={navigate} status={status} />
        <LandingPage onNavigate={navigate} />
      </div>
    );
  }

  // ROUTE 2: NOT FOUND (404 Page)
  if (route.view === 'not-found') {
    return (
      <div className="app-root mode-landing">
        <Navbar currentPath={window.location.pathname} onNavigate={navigate} status={status} />
        <NotFoundView onNavigate={navigate} />
      </div>
    );
  }

  // ROUTE 3: CONSOLE / DEVELOPER WORKSPACE (/console)
  return (
    <div className="dev-workspace">
      {/* Universal Sidebar */}
      <Sidebar
        activePage={route.page}
        setActivePage={(pageId) => navigate(`/console/${pageId}`)}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      />

      <div className="dev-main">
        {/* Universal Top Header */}
        <Header
          health={health}
          activeApp={activeAppName}
          activePage={route.page}
          onDownloadReport={() => { window.location.href = '/report/current'; }}
          wsStatus={wsStatus}
          runStatus={status}
          onNavigateHome={() => navigate('/')}
          onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          isSidebarCollapsed={isSidebarCollapsed}
        />

        {/* Dynamic Page Content with Progressive Loading */}
        <div className="dev-content-scroll">
          <ErrorBoundary key={route.page} onReset={() => navigate('/console/overview')}>
            {loading && !hasLoadedConsoleDataRef.current ? (
              <ConsoleSkeleton />
            ) : (
              <>
                {route.page === 'overview' && (
                  <OverviewView
                    summary={summary}
                    health={health}
                    iterations={iterations}
                    loading={loading}
                    error={errorMsg}
                    onRefresh={() => fetchConsoleData(true)}
                    onNavigate={(pageId) => navigate(`/console/${pageId}`)}
                  />
                )}

                {route.page === 'experiments' && (
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

                {route.page === 'trials' && (
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

                {route.page === 'applications' && (
                  <ApplicationsView
                    adapters={adapters}
                    onRefresh={() => fetchConsoleData(true)}
                  />
                )}

                {route.page === 'evaluations' && (
                  <EvaluationAnalyticsView
                    iterations={iterations}
                    holdoutScore={holdoutScore}
                    bestConfig={bestConfig}
                    onDownloadReport={() => { window.location.href = '/report/current'; }}
                  />
                )}

                {route.page === 'optimization' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                    <div>
                      <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-ink)', margin: 0 }}>
                        Hybrid Optimization Architecture
                      </h1>
                      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', margin: 'var(--space-2xs) 0 0 0' }}>
                        Optuna TPE Bayesian exploration coupled with local LLM failure diagnosis.
                      </p>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-sm)' }}>
                      <MetricCard title="Bayesian Engine" value="Optuna TPE" subtitle="SQLite persistent study" icon={Sliders} color="var(--color-accent)" />
                      <MetricCard title="Diagnostician" value="Qwen 2.5 1.5B" subtitle="Ollama local LLM reasoning" icon={Cpu} color="var(--color-cool)" />
                      <MetricCard title="Generator" value="Llama 3.2 3B" subtitle="Target RAG response generator" icon={Terminal} color="var(--color-cool)" />
                    </div>
                  </div>
                )}

                {route.page === 'promotions' && (
                  <PromotionsView
                    bestConfig={bestConfig}
                    holdoutScore={holdoutScore}
                    adapters={adapters}
                    onRefresh={() => fetchConsoleData(true)}
                  />
                )}

                {route.page === 'settings' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                    <div>
                      <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-ink)', margin: 0 }}>
                        System Settings &amp; Connectivity
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
                            {health?.generator?.model || (typeof health?.generator === 'string' ? health.generator : 'llama3.2:latest')}
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
              </>
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
