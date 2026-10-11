// OvaCare AI — thin fetch() wrapper around the backend REST API.
// Framework-free on purpose (see docs/deployment.md — npm's registry was
// not reachable in this project's development environment, so the web
// app is plain HTML/CSS/JS rather than a bundled framework app).

const OvaCareAPI = (() => {
  const BASE = window.OVACARE_CONFIG.API_BASE_URL;
  const TOKEN_KEY = "ovacare_access_token";
  const REFRESH_KEY = "ovacare_refresh_token";

  function getAccessToken() {
    return window.localStorage.getItem(TOKEN_KEY);
  }
  function getRefreshToken() {
    return window.localStorage.getItem(REFRESH_KEY);
  }
  function setTokens({ access_token, refresh_token }) {
    if (access_token) window.localStorage.setItem(TOKEN_KEY, access_token);
    if (refresh_token) window.localStorage.setItem(REFRESH_KEY, refresh_token);
  }
  function clearTokens() {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  }
  function isAuthenticated() {
    return Boolean(getAccessToken());
  }

  async function _request(method, path, body, { auth = true, retry = true } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (auth && getAccessToken()) {
      headers["Authorization"] = `Bearer ${getAccessToken()}`;
    }
    const response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401 && auth && retry && getRefreshToken()) {
      // Access token likely expired — try the refresh flow once, then retry.
      const refreshed = await _tryRefresh();
      if (refreshed) {
        return _request(method, path, body, { auth, retry: false });
      }
      clearTokens();
    }

    let data = null;
    const text = await response.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (e) {
        data = { detail: text };
      }
    }

    if (!response.ok) {
      const message = (data && (data.detail || data.message)) || "Something went wrong. Please try again.";
      const error = new Error(message);
      error.status = response.status;
      error.body = data;
      throw error;
    }
    return data;
  }

  async function _tryRefresh() {
    try {
      const data = await _request("POST", "/auth/refresh", { refresh_token: getRefreshToken() }, { auth: false, retry: false });
      setTokens(data);
      return true;
    } catch (e) {
      return false;
    }
  }

  return {
    isAuthenticated,
    clearTokens,

    // --- Auth ---
    register: (email, password) => _request("POST", "/auth/register", { email, password }, { auth: false }).then(setTokens),
    login: (email, password) => _request("POST", "/auth/login", { email, password }, { auth: false }).then(setTokens),
    logout: () => _request("POST", "/auth/logout", { refresh_token: getRefreshToken() }).finally(clearTokens),
    forgotPassword: (email) => _request("POST", "/auth/forgot-password", { email }, { auth: false }),

    // --- Profile ---
    getMe: () => _request("GET", "/users/me"),
    updateMe: (payload) => _request("PUT", "/users/me", payload),
    deleteMe: () => _request("DELETE", "/users/me"),

    // --- Consent ---
    getConsents: () => _request("GET", "/consent"),
    submitConsent: (payload) => _request("POST", "/consent", payload),
    withdrawConsent: (consentType) => _request("PUT", `/consent/${consentType}`),

    // --- Cycles ---
    listCycles: () => _request("GET", "/cycles"),
    createCycle: (payload) => _request("POST", "/cycles", payload),
    updateCycle: (id, payload) => _request("PUT", `/cycles/${id}`, payload),
    deleteCycle: (id) => _request("DELETE", `/cycles/${id}`),
    cycleSummary: () => _request("GET", "/cycles/summary"),
    cycleEstimate: () => _request("GET", "/cycles/estimate"),

    // --- Symptoms ---
    listSymptoms: () => _request("GET", "/symptoms"),
    createSymptom: (payload) => _request("POST", "/symptoms", payload),
    deleteSymptom: (id) => _request("DELETE", `/symptoms/${id}`),

    // --- Assessments / predictions ---
    submitAssessment: (payload) => _request("POST", "/assessments", payload),
    listAssessments: () => _request("GET", "/assessments"),
    requestPrediction: (assessmentId) => _request("POST", "/predictions", { assessment_id: assessmentId }),
    predictionHistory: () => _request("GET", "/predictions/history"),

    // --- Insights / reports ---
    getInsights: () => _request("GET", "/insights"),
    getReport: () => _request("GET", "/reports"),
    // Binary response — can't go through _request()'s JSON parsing. Returns
    // a Blob the caller can save via URL.createObjectURL (see downloadBlob
    // in app.js). GET /reports (JSON, above) is unchanged; this is additive.
    downloadReportPdf: async () => {
      const response = await fetch(`${BASE}/reports/pdf`, {
        headers: getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {},
      });
      if (!response.ok) {
        let message = "Something went wrong. Please try again.";
        try {
          const data = await response.json();
          message = data.detail || message;
        } catch (e) {
          /* non-JSON error body — keep the generic message */
        }
        const error = new Error(message);
        error.status = response.status;
        throw error;
      }
      return response.blob();
    },

    // --- Notifications ---
    getNotificationPreferences: () => _request("GET", "/notifications/preferences"),
    updateNotificationPreferences: (payload) => _request("PUT", "/notifications/preferences", payload),
  };
})();
