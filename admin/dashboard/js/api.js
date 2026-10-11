// OvaCare AI — Admin portal API client. Deliberately narrow: it only
// knows how to call the /auth/* endpoints (to obtain a token) and the
// /admin/* endpoints (requirement #30 — every route behind those is
// server-side RBAC-gated to the ADMIN role; this client adds no
// authorization logic of its own, it just surfaces what the backend
// returns or refuses).

const OvaCareAdminAPI = (() => {
  const BASE = window.OVACARE_ADMIN_CONFIG.API_BASE_URL;
  const TOKEN_KEY = "ovacare_admin_access_token";
  const REFRESH_KEY = "ovacare_admin_refresh_token";

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

    // The admin portal signs in through the same /auth/login endpoint
    // every account uses — there is no separate admin login route.
    // Authorization is enforced per-request by require_admin() on the
    // backend: a non-admin account will authenticate fine here and then
    // get a 403 on the very first /admin/* call. login() itself cannot
    // tell the difference; callers must confirm admin access afterwards
    // (see app.js, which probes /admin/system-health right after login).
    login: (email, password) => _request("POST", "/auth/login", { email, password }, { auth: false }).then(setTokens),
    logout: () => _request("POST", "/auth/logout", { refresh_token: getRefreshToken() }).finally(clearTokens),

    listUsers: (limit = 50, offset = 0) => _request("GET", `/admin/users?limit=${limit}&offset=${offset}`),
    listModels: () => _request("GET", "/admin/models"),
    systemHealth: () => _request("GET", "/admin/system-health"),
    monitoring: (windowDays = 30) => _request("GET", `/admin/monitoring?window_days=${windowDays}`),
    auditLogs: (limit = 100, offset = 0) => _request("GET", `/admin/audit-logs?limit=${limit}&offset=${offset}`),
  };
})();
