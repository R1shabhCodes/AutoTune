/**
 * Centralized API client for AutoTune 2.0 Dashboard.
 * Interacts with real FastAPI routes and safely parses JSON with:
 * - In-flight request deduplication (prevents duplicate concurrent calls)
 * - Session-level in-memory cache with configurable TTL
 * - Graceful timeout handling (default 10s) and abort signal propagation
 * - Pre-warming utility for seamless progressive loading
 */

const DEFAULT_TIMEOUT_MS = 10000;

// In-memory cache for session read-only telemetry
const cacheStore = new Map();
// In-flight promise tracker for request deduplication
const inFlightRequests = new Map();

async function request(endpoint, options = {}) {
  const {
    timeout = DEFAULT_TIMEOUT_MS,
    useCache = false,
    cacheTTL = 30000, // 30 seconds default TTL
    forceRefresh = false,
    signal = null,
    headers = {},
    ...fetchOptions
  } = options;

  const isGet = !fetchOptions.method || fetchOptions.method.toUpperCase() === 'GET';

  // 1. Check in-memory cache if applicable
  if (isGet && useCache && !forceRefresh) {
    const cached = cacheStore.get(endpoint);
    if (cached && (Date.now() - cached.timestamp < cacheTTL)) {
      return cached.data;
    }
  }

  // 2. Check in-flight promise deduplication
  if (isGet && !forceRefresh && inFlightRequests.has(endpoint)) {
    return inFlightRequests.get(endpoint);
  }

  // 3. Set up AbortController with timeout and parent signal bridging
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId);
      controller.abort();
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
  }

  const executeFetch = async () => {
    try {
      const res = await fetch(endpoint, {
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...headers
        },
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
        try {
          const errJson = await res.json();
          if (errJson.detail) errorDetail = errJson.detail;
          else if (errJson.message) errorDetail = errJson.message;
        } catch (_) {
          // Fallback to HTTP text
        }
        throw new Error(errorDetail);
      }

      const data = await res.json();

      // Store in memory cache if enabled
      if (isGet && useCache) {
        cacheStore.set(endpoint, { data, timestamp: Date.now() });
      }

      return data;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        throw new Error(`Request timed out after ${timeout}ms: ${endpoint}`);
      }
      throw err;
    } finally {
      inFlightRequests.delete(endpoint);
    }
  };

  const fetchPromise = executeFetch();
  if (isGet) {
    inFlightRequests.set(endpoint, fetchPromise);
  }

  return fetchPromise;
}

export const api = {
  // 1. System & Model Health (cached 15s)
  getHealth: (opts = {}) => request('/health/status', { useCache: true, cacheTTL: 15000, ...opts }),

  // 2. Real Overview Metrics Summary (cached 30s)
  getOverviewSummary: (opts = {}) => request('/overview/summary', { useCache: true, cacheTTL: 30000, ...opts }),

  // 3. Iteration History
  getIterations: (experimentId = null, opts = {}) => {
    const query = experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : '';
    return request(`/iterations${query}`, { useCache: true, cacheTTL: 10000, ...opts });
  },

  // 3b. Experiment Study Summaries
  getExperiments: (opts = {}) => request('/experiments', { useCache: true, cacheTTL: 20000, ...opts }),

  // 4. Best Active Configuration
  getBestConfig: (experimentId = null, opts = {}) => {
    const query = experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : '';
    return request(`/best${query}`, { useCache: true, cacheTTL: 15000, ...opts });
  },

  // 5. Holdout Evaluation Score (Triggered strictly on-demand)
  getHoldoutScore: (opts = {}) => request('/holdout_score', { timeout: 30000, ...opts }),

  // 6. Registered Applications & Adapters (cached 60s)
  getAdapters: (opts = {}) => request('/integrations/adapters', { useCache: true, cacheTTL: 60000, ...opts }),

  // 6b. Single Adapter Detail (manifest + current config + health)
  getAdapterDetail: (adapterId, opts = {}) => request(`/integrations/adapters/${encodeURIComponent(adapterId)}`, { useCache: true, cacheTTL: 30000, ...opts }),

  // 7. Connect Remote RAG Endpoint
  connectAdapter: (payload, opts = {}) => request('/integrations/connect', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...opts
  }),

  // 8. Start Optimization Run
  startRun: (payload, opts = {}) => request('/run', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...opts
  }),

  // 9. Per-question Granular Evaluations
  getTrialEvaluations: (trialId, opts = {}) => request(`/trials/${encodeURIComponent(trialId)}/evaluations`, { useCache: true, cacheTTL: 60000, ...opts }),

  // 10. Promotion Qualification Check
  evaluatePromotion: (payload, opts = {}) => request('/promotion/evaluate', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeout: 30000,
    ...opts
  }),

  // 11. Explicit Promotion Action
  promoteConfig: (payload, opts = {}) => request('/promotion/promote', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...opts
  }),

  // 12. WebSocket URL Helper
  getWebSocketUrl: () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    if (host.includes('5173')) {
      return 'ws://localhost:8000/ws';
    }
    return `${protocol}//${host}/ws`;
  },

  // 13. Preload telemetry for progressive loading (runs non-blocking in idle callback)
  preloadTelemetry: async () => {
    try {
      await Promise.allSettled([
        api.getHealth(),
        api.getOverviewSummary(),
        api.getAdapters()
      ]);
    } catch (_) {
      // Non-fatal pre-warming
    }
  },

  // 14. Cache invalidation helper
  invalidateCache: (endpointPrefix = null) => {
    if (!endpointPrefix) {
      cacheStore.clear();
      return;
    }
    for (const key of cacheStore.keys()) {
      if (key.startsWith(endpointPrefix)) {
        cacheStore.delete(key);
      }
    }
  }
};
