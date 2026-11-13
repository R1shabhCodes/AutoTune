import React, { useState, useEffect, useCallback } from 'react';
import {
  Server, Layers, ChevronRight, ChevronDown, PlugZap, AlertCircle,
  CheckCircle2, Info, RefreshCw, ExternalLink, Lock, Sliders,
  X, Eye, Settings2
} from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import EmptyState from '../components/common/EmptyState';
import { api } from '../api/client';

/** Capability flag row displayed in adapter details */
function CapabilityRow({ label, supported, description }) {
  return (
    <div className="app-capability-row">
      <div className="app-capability-name">
        {supported
          ? <CheckCircle2 size={12} style={{ color: 'var(--color-ok)', flexShrink: 0 }} />
          : <X size={12} style={{ color: 'var(--color-muted)', flexShrink: 0 }} />
        }
        <span style={{ color: supported ? 'var(--color-ink)' : 'var(--color-muted)' }}>
          {label}
        </span>
      </div>
      {description && (
        <span className="app-capability-desc">{description}</span>
      )}
    </div>
  );
}

/** Displays a single parameter schema row in the detail drawer */
function ParameterRow({ name, schema }) {
  const rangeText = (() => {
    if (schema.options) return schema.options.join(' · ');
    if (schema.min !== undefined && schema.max !== undefined) {
      const step = schema.step ? ` step ${schema.step}` : '';
      return `${schema.min} – ${schema.max}${step}`;
    }
    return null;
  })();

  return (
    <div className="app-param-row">
      <div className="app-param-header">
        <span className="app-param-name mono-nums">{name}</span>
        <span className="app-param-type-badge">{schema.type}</span>
      </div>
      <div className="app-param-meta">
        <span className="app-param-current">
          Current: <span className="mono-nums">{String(schema.current ?? schema.default)}</span>
        </span>
        {rangeText && (
          <span className="app-param-range mono-nums">{rangeText}</span>
        )}
      </div>
      {schema.description && (
        <p className="app-param-desc">{schema.description}</p>
      )}
    </div>
  );
}

/** Adapter detail drawer — full manifest, params, config, health */
function AdapterDrawer({ adapterId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!adapterId) return;
    setLoading(true);
    setError(null);
    api.getAdapterDetail(adapterId)
      .then(setDetail)
      .catch(err => setError(err.message || 'Failed to load adapter detail'))
      .finally(() => setLoading(false));
  }, [adapterId]);

  const capabilityLabels = {
    query: 'Query execution',
    apply_config: 'Dynamic config updates',
    restore_config: 'Configuration restore',
    validate_config: 'Config pre-validation',
    rebuild_index: 'Index rebuild / switch',
    contexts_exposed: 'Retrieved contexts',
    scores_exposed: 'Retrieval confidence scores',
    usage_exposed: 'Token usage',
    citations_exposed: 'Citation references',
  };

  return (
    <aside className="app-drawer" aria-label="Adapter details" role="complementary">
      <div className="app-drawer-header">
        <div className="app-drawer-title-group">
          <Settings2 size={16} style={{ color: 'var(--color-cool)' }} />
          <span className="app-drawer-title">
            {detail ? detail.application : adapterId}
          </span>
          {detail && <StatusBadge status={detail.mode} label={detail.mode} />}
        </div>
        <button
          type="button"
          className="app-drawer-close"
          onClick={onClose}
          aria-label="Close adapter details"
        >
          <X size={15} />
        </button>
      </div>

      <div className="app-drawer-scroll">
        {loading && (
          <div className="app-drawer-loading">
            <RefreshCw size={18} className="animate-spin" style={{ color: 'var(--color-muted)' }} />
            <span>Loading adapter details…</span>
          </div>
        )}

        {error && (
          <div className="error-callout" role="alert">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && detail && (
          <>
            {/* Application Identity */}
            <section className="app-drawer-section">
              <h3 className="app-drawer-section-title">Application</h3>
              <div className="app-detail-grid">
                <div className="app-detail-row">
                  <span className="app-detail-label">Name</span>
                  <span className="app-detail-value">{detail.application}</span>
                </div>
                <div className="app-detail-row">
                  <span className="app-detail-label">Version</span>
                  <span className="app-detail-value mono-nums">{detail.version}</span>
                </div>
                <div className="app-detail-row">
                  <span className="app-detail-label">Protocol</span>
                  <span className="app-detail-value mono-nums">AutoTune {detail.integration_version}</span>
                </div>
                <div className="app-detail-row">
                  <span className="app-detail-label">Mode</span>
                  <div>
                    <StatusBadge status={detail.mode} label={detail.mode} />
                  </div>
                </div>
                <div className="app-detail-row">
                  <span className="app-detail-label">Health</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2xs)' }}>
                    <StatusBadge
                      status={detail.health_status === 'healthy' ? 'healthy' : detail.health_status === 'unknown' ? 'idle' : 'degraded'}
                      label={detail.health_status}
                    />
                    {detail.health_message && (
                      <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--color-muted)' }}>
                        ({detail.health_message})
                      </span>
                    )}
                  </div>
                </div>
                {detail.description && (
                  <div className="app-detail-row" style={{ gridColumn: '1 / -1' }}>
                    <span className="app-detail-label">Description</span>
                    <span className="app-detail-value" style={{ color: 'var(--color-ink-muted)' }}>
                      {detail.description}
                    </span>
                  </div>
                )}
              </div>
            </section>

            {/* Capabilities */}
            <section className="app-drawer-section">
              <h3 className="app-drawer-section-title">Capabilities</h3>
              <div className="app-capability-list">
                {Object.entries(detail.capabilities).map(([key, val]) => (
                  <CapabilityRow
                    key={key}
                    label={capabilityLabels[key] || key}
                    supported={val}
                  />
                ))}
              </div>
            </section>

            {/* Limitations notice for observe-mode adapters */}
            {detail.mode === 'observe' && (
              <div className="app-limitation-notice" role="note">
                <Lock size={12} style={{ flexShrink: 0 }} />
                <span>
                  This adapter is in <strong>observe mode</strong>. AutoTune can query and
                  evaluate this application but cannot apply, validate, or restore
                  configuration parameters. To enable full optimization, re-register the
                  adapter with <code>apply_config: true</code> in its manifest.
                </span>
              </div>
            )}

            {/* Tunable Parameters */}
            {Object.keys(detail.parameters).length > 0 ? (
              <section className="app-drawer-section">
                <h3 className="app-drawer-section-title">
                  Tunable parameters
                  <span className="item-count-badge mono-nums" style={{ marginLeft: 'var(--space-xs)' }}>
                    {Object.keys(detail.parameters).length}
                  </span>
                </h3>
                <div className="app-param-list">
                  {Object.entries(detail.parameters).map(([name, schema]) => (
                    <ParameterRow key={name} name={name} schema={schema} />
                  ))}
                </div>
              </section>
            ) : (
              <section className="app-drawer-section">
                <h3 className="app-drawer-section-title">Tunable parameters</h3>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', margin: 0 }}>
                  No parameters declared in manifest.
                </p>
              </section>
            )}

            {/* Current Active Config */}
            {Object.keys(detail.current_config || {}).length > 0 && (
              <section className="app-drawer-section">
                <h3 className="app-drawer-section-title">Active configuration</h3>
                <div className="app-config-snapshot">
                  {Object.entries(detail.current_config).map(([k, v]) => (
                    <div key={k} className="app-config-row">
                      <span className="app-config-key mono-nums">{k}</span>
                      <span className="app-config-val mono-nums">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Backend gap notice */}
            <div className="app-gap-notice" role="note">
              <Info size={12} style={{ flexShrink: 0 }} />
              <span>
                Adapter registration, deletion, and mode switching are not exposed by the
                current backend. To register a new external RAG endpoint, use
                the <strong>Connect endpoint</strong> form below. Editing or removing adapters
                requires a backend Stage 5 implementation.
              </span>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

/** Connect form for registering a new REST RAG endpoint */
function ConnectEndpointForm({ onConnect, connecting, connectError, connectResult }) {
  const [expanded, setExpanded] = useState(false);
  const [form, setForm] = useState({
    id: '',
    base_url: '',
    api_key: '',
    timeout: '10',
    set_active: false,
  });

  const handleChange = (field, value) => setForm(f => ({ ...f, [field]: value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.base_url) return;
    onConnect({
      id: form.id || undefined,
      base_url: form.base_url,
      api_key: form.api_key || undefined,
      timeout: parseFloat(form.timeout) || 10,
      set_active: form.set_active,
    });
  };

  return (
    <section className="console-panel app-connect-panel">
      <button
        type="button"
        className="app-connect-toggle"
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
          <PlugZap size={15} style={{ color: 'var(--color-cool)' }} />
          <span className="app-connect-toggle-label" style={{ whiteSpace: 'nowrap' }}>Connect endpoint</span>
        </div>
        {expanded
          ? <ChevronDown size={14} style={{ color: 'var(--color-muted)' }} />
          : <ChevronRight size={14} style={{ color: 'var(--color-muted)' }} />
        }
      </button>

      {expanded && (
        <form className="app-connect-form" onSubmit={handleSubmit} noValidate>
          <p className="app-connect-info">
            Registers a remote RAG service conforming to the AutoTune REST protocol.
            The endpoint must expose <code>/autotune/manifest</code> and <code>/autotune/query</code>.
          </p>

          <div className="app-form-row">
            <label className="app-form-label" htmlFor="conn-id">Adapter ID</label>
            <input
              id="conn-id"
              type="text"
              className="app-form-input"
              placeholder="e.g. my-rag-service"
              value={form.id}
              onChange={e => handleChange('id', e.target.value)}
              autoComplete="off"
            />
          </div>

          <div className="app-form-row">
            <label className="app-form-label" htmlFor="conn-url">
              Base URL <span style={{ color: 'var(--color-bad)' }}>*</span>
            </label>
            <input
              id="conn-url"
              type="url"
              className="app-form-input"
              placeholder="http://localhost:5050"
              value={form.base_url}
              onChange={e => handleChange('base_url', e.target.value)}
              required
              autoComplete="off"
            />
          </div>

          <div className="app-form-row">
            <label className="app-form-label" htmlFor="conn-key">API key (optional)</label>
            <input
              id="conn-key"
              type="password"
              className="app-form-input"
              placeholder="Bearer token"
              value={form.api_key}
              onChange={e => handleChange('api_key', e.target.value)}
              autoComplete="new-password"
            />
          </div>

          <div className="app-form-row app-form-row-inline">
            <div style={{ flex: 1 }}>
              <label className="app-form-label" htmlFor="conn-timeout">Timeout (seconds)</label>
              <input
                id="conn-timeout"
                type="number"
                className="app-form-input"
                min="1"
                max="60"
                step="0.5"
                value={form.timeout}
                onChange={e => handleChange('timeout', e.target.value)}
              />
            </div>
            <label className="app-form-checkbox-label">
              <input
                type="checkbox"
                checked={form.set_active}
                onChange={e => handleChange('set_active', e.target.checked)}
              />
              <span>Set as active adapter</span>
            </label>
          </div>

          {connectError && (
            <div className="error-callout" role="alert">
              <AlertCircle size={13} />
              <span>{connectError}</span>
            </div>
          )}

          {connectResult && (
            <div className="app-connect-success" role="status">
              <CheckCircle2 size={13} style={{ color: 'var(--color-ok)' }} />
              <span>
                Connected: <strong>{connectResult.application}</strong> ({connectResult.adapter_id}),
                {connectResult.parameters?.length ?? 0} parameters, mode: {connectResult.mode}
              </span>
            </div>
          )}

          <div className="app-form-actions">
            <button
              type="submit"
              className="app-connect-submit-btn"
              disabled={connecting || !form.base_url}
            >
              {connecting
                ? <><RefreshCw size={12} className="animate-spin" aria-label="Connecting" /> <span style={{ whiteSpace: 'nowrap' }}>Connecting</span></>
                : <><ExternalLink size={12} /> <span style={{ whiteSpace: 'nowrap' }}>Connect</span></>
              }
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

/** Adapter list card — summary row */
function AdapterCard({ adapterId, meta, isSelected, onClick }) {
  const paramCount = Array.isArray(meta.parameters) ? meta.parameters.length : Object.keys(meta.parameters || {}).length;

  return (
    <article
      className={`app-adapter-card console-panel ${isSelected ? 'is-selected' : ''} ${meta.is_active ? 'is-active' : ''}`}
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      onClick={() => onClick(adapterId)}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onClick(adapterId)}
    >
      <div className="app-card-header">
        <div className="app-card-identity">
          <div className="app-card-icon-wrap">
            <Server size={15} style={{ color: meta.is_active ? 'var(--color-cool)' : 'var(--color-muted)' }} />
          </div>
          <div className="app-card-title-group">
            <span className="app-card-name">{meta.application || adapterId}</span>
            <span className="app-card-id mono-nums">{adapterId}</span>
          </div>
        </div>
        <div className="app-card-badges">
          {meta.is_active && (
            <StatusBadge status="healthy" label="Active" />
          )}
          <StatusBadge status={meta.mode || 'optimize'} label={meta.mode || 'optimize'} />
        </div>
      </div>

      <div className="app-card-meta-strip">
        <div className="app-card-meta-item">
          <Sliders size={11} style={{ color: 'var(--color-muted)' }} />
          <span>{paramCount} tunable {paramCount === 1 ? 'parameter' : 'parameters'}</span>
        </div>

        {meta.capabilities?.apply_config
          ? <div className="app-card-meta-item">
              <Settings2 size={11} style={{ color: 'var(--color-ok)' }} />
              <span style={{ color: 'var(--color-ok)' }}>Config mutable</span>
            </div>
          : <div className="app-card-meta-item">
              <Lock size={11} style={{ color: 'var(--color-muted)' }} />
              <span>Read-only</span>
            </div>
        }

        {meta.capabilities?.query && (
          <div className="app-card-meta-item">
            <Eye size={11} style={{ color: 'var(--color-cool)' }} />
            <span style={{ color: 'var(--color-cool)' }}>Queryable</span>
          </div>
        )}
      </div>

      <div className="app-card-chevron" aria-hidden="true">
        <ChevronRight size={14} style={{ color: 'var(--color-muted)' }} />
      </div>
    </article>
  );
}

/** Main ApplicationsView */
export default function ApplicationsView({ adapters, onRefresh }) {
  const [adapterMap, setAdapterMap] = useState({});
  const [loadingMap, setLoadingMap] = useState(true);
  const [mapError, setMapError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  // Connect form state
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState(null);
  const [connectResult, setConnectResult] = useState(null);

  // Fetch the richer adapter list from API
  const fetchAdapterMap = useCallback(() => {
    setLoadingMap(true);
    setMapError(null);
    api.getAdapters()
      .then(data => {
        // Backend returns { adapter_id: { application, mode, ... }, ... }
        if (data && typeof data === 'object' && !Array.isArray(data)) {
          setAdapterMap(data);
        } else if (Array.isArray(data)) {
          const map = {};
          data.forEach(a => { map[a.adapter_id || a.id] = a; });
          setAdapterMap(map);
        }
      })
      .catch(err => setMapError(err.message || 'Failed to load adapters'))
      .finally(() => setLoadingMap(false));
  }, []);

  useEffect(() => {
    fetchAdapterMap();
  }, [fetchAdapterMap, adapters]);

  const handleConnect = async (payload) => {
    setConnecting(true);
    setConnectError(null);
    setConnectResult(null);
    try {
      const result = await api.connectAdapter(payload);
      setConnectResult(result);
      fetchAdapterMap();
      if (onRefresh) onRefresh();
    } catch (err) {
      setConnectError(err.message || 'Connection failed. Verify the endpoint is reachable.');
    } finally {
      setConnecting(false);
    }
  };

  const adapterEntries = Object.entries(adapterMap);
  const hasAdapters = adapterEntries.length > 0;

  return (
    <div className="applications-view-root">
      {/* Page Header */}
      <div className="page-header-block">
        <div className="page-title-group">
          <div className="page-title-row">
            <Layers size={18} style={{ color: 'var(--color-cool)' }} />
            <h1 className="page-title">Connected applications</h1>
          </div>
          <p className="page-subtitle">
            Registered RAG adapters and their optimization capabilities. Select an adapter to inspect its manifest, parameters, and current configuration.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
          <button
            type="button"
            className="console-btn-wizard"
            onClick={() => { fetchAdapterMap(); if (onRefresh) onRefresh(); }}
            title="Refresh adapter list"
          >
            <RefreshCw size={12} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {mapError && (
        <div className="error-callout" role="alert">
          <AlertCircle size={14} />
          <span>{mapError}</span>
        </div>
      )}

      <div className={`applications-layout ${selectedId ? 'has-drawer' : ''}`}>
        {/* Left column: Adapter list */}
        <div className="app-list-column">
          {loadingMap ? (
            <div className="app-loading-state">
              <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--color-muted)' }} />
              <span>Loading registered adapters…</span>
            </div>
          ) : !hasAdapters ? (
            <EmptyState
              title="No adapters registered"
              description="AutoTune starts with the built-in Finance RAG adapter. Connect an external RAG endpoint using the form below."
            />
          ) : (
            <div className="app-card-list">
              {adapterEntries.map(([id, meta]) => (
                <AdapterCard
                  key={id}
                  adapterId={id}
                  meta={meta}
                  isSelected={selectedId === id}
                  onClick={(aid) => setSelectedId(prev => prev === aid ? null : aid)}
                />
              ))}
            </div>
          )}

          {/* Connect form always visible below list */}
          <ConnectEndpointForm
            onConnect={handleConnect}
            connecting={connecting}
            connectError={connectError}
            connectResult={connectResult}
          />
        </div>

        {/* Right column: Detail drawer (conditional) */}
        {selectedId && (
          <AdapterDrawer
            adapterId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </div>
  );
}
