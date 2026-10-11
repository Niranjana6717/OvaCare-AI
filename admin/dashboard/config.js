// OvaCare AI — Admin portal configuration.
// No build step. Change API_BASE_URL to point at a running backend.
window.OVACARE_ADMIN_CONFIG = {
  API_BASE_URL: window.localStorage.getItem("ovacare_admin_api_base_url") || "http://localhost:8000/api/v1",
};
