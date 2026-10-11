// OvaCare AI — Web app configuration.
// No build step: this file is loaded directly by index.html. Change
// API_BASE_URL to point at a running backend (see backend/README / the
// root docs/deployment.md for how to run one).
window.OVACARE_CONFIG = {
  API_BASE_URL: window.localStorage.getItem("ovacare_api_base_url") || "http://localhost:8000/api/v1",
};
