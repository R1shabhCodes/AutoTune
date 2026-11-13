/**
 * Centralized API client for AutoTune 2.0 Dashboard.
 * Interacts with real FastAPI routes and safely parses JSON with timeout support.
 */

const DEFAULT_TIMEOUT_MS = 15000;

async function request(endpoint, options = {}) {
  const { timeout = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options;

  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(endpoint, {
      ...fetchOptions,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...(fetchOptions.headers || {})
      },
      signal: controller.signal
    });

    clearTimeout(id);

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

    return await res.json();
  } catch (err) {
    clearTimeout(id);
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeout}ms: ${endpoint}`);
    }
    throw err;
  }
}

export const api = {
  // 1. System & Model Health
  getHealth: () => request('/health/status'),

  // 2. Real Overview Metrics Summary
  getOverviewSummary: () => request('/overview/summary'),

  // 3. Iteration History
  getIterations: (experimentId = null) => {
    const query = experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : '';
    return request(`/iterations${query}`);
  },

  // 3b. Experiment Study Summaries
  getExperiments: () => request('/experiments'),

  // 4. Best Active Configuration
  getBestConfig: (experimentId = null) => {
    const query = experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : '';
    return request(`/best${query}`);
  },

  // 5. Holdout Evaluation Score
  getHoldoutScore: () => request('/holdout_score'),

  // 6. Registered Applications & Adapters
  getAdapters: () => request('/integrations/adapters'),

  // 6b. Single Adapter Detail (manifest + current config + health)
  getAdapterDetail: (adapterId) => request(`/integrations/adapters/${encodeURIComponent(adapterId)}`),

  // 7. Connect Remote RAG Endpoint
  connectAdapter: (payload) => request('/integrations/connect', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),

  // 8. Start Optimization Run
  startRun: (payload) => request('/run', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),

  // 9. Per-question Granular Evaluations
  getTrialEvaluations: (trialId) => request(`/trials/${encodeURIComponent(trialId)}/evaluations`),

  // 10. Promotion Qualification Check
  evaluatePromotion: (payload) => request('/promotion/evaluate', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),

  // 11. Explicit Promotion Action
  promoteConfig: (payload) => request('/promotion/promote', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),

  // 12. WebSocket URL Helper
  getWebSocketUrl: () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    if (host.includes('5173')) {
      return 'ws://localhost:8000/ws';
    }
    return `${protocol}//${host}/ws`;
  }
};

