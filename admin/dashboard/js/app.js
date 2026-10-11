// OvaCare AI — Admin portal router/views. Static HTML/CSS/vanilla JS,
// same no-build-step pattern as apps/web (see docs/deployment.md).
//
// Design constraint that shapes every view in this file (requirement
// #30 / #40): the admin portal shows account and system metadata only.
// It never renders a user's cycle records, symptoms, assessment
// responses, predictions, or free-text explanations — not because the
// UI hides fields, but because the /admin/* endpoints it calls never
// return them in the first place (see backend/app/api/admin.py). A
// "Restricted by design" note is repeated on the relevant screens so
// that's visible to whoever is using this, not just true in the API.

const ADMIN_NAV_ITEMS = [
  { hash: "#/users", label: "Users" },
  { hash: "#/models", label: "Model Versions" },
  { hash: "#/monitoring", label: "ML Monitoring" },
  { hash: "#/system-health", label: "System Health" },
  { hash: "#/audit-logs", label: "Audit Logs" },
];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderShell() {
  document.getElementById("app").innerHTML = `
    <nav class="sidebar">
      <div class="brand">OvaCare AI</div>
      <div class="brand-sub">Admin Portal</div>
      ${ADMIN_NAV_ITEMS.map((item) => `<a class="nav-link" data-hash="${item.hash}" href="${item.hash}">${item.label}</a>`).join("")}
      <a class="nav-link" id="logout-link" href="#">Log out</a>
    </nav>
    <main class="content" id="view"></main>
  `;
  document.getElementById("logout-link").addEventListener("click", async (e) => {
    e.preventDefault();
    try { await OvaCareAdminAPI.logout(); } catch (err) { /* clear regardless */ }
    location.hash = "#/login";
  });
}

function setActiveNav(hash) {
  document.querySelectorAll(".nav-link[data-hash]").forEach((el) => {
    el.classList.toggle("active", el.dataset.hash === hash);
  });
}

function mount(html) {
  document.getElementById("view").innerHTML = html;
}

function bannerFor(error) {
  if (!error) return "";
  if (error.status === 403) {
    return `<div class="banner danger">Your account does not have admin access, or your session has expired. ${escapeHtml(error.message)}</div>`;
  }
  return `<div class="banner danger">${escapeHtml(error.message)}</div>`;
}

const RESTRICTED_NOTE = `<p class="restricted-note">Restricted by design: health data — cycle records, symptoms, assessment
  responses, and screening predictions — is never exposed through the admin portal or its API routes. Only account and
  system metadata is available here (requirement #30 / #40).</p>`;

// ---------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------

function viewLogin() {
  mount(`
    <div class="auth-shell">
      <div class="card">
        <h2>Admin sign in</h2>
        <p class="muted">This is the same account system as the OvaCare app. Only accounts with the
          <strong>admin</strong> role can access anything past this screen.</p>
        <div id="login-error"></div>
        <form id="login-form">
          <label for="email">Email</label>
          <input id="email" type="email" required autocomplete="username" />
          <label for="password">Password</label>
          <input id="password" type="password" required autocomplete="current-password" />
          <div style="margin-top: 20px;">
            <button class="btn" type="submit">Sign in</button>
          </div>
        </form>
      </div>
    </div>
  `);

  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const errorEl = document.getElementById("login-error");
    errorEl.innerHTML = "";
    try {
      await OvaCareAdminAPI.login(email, password);
      // login() only proves the credentials are valid — it says nothing
      // about role. Probe an admin-only endpoint before treating this as
      // a successful admin sign-in, and roll back cleanly if it isn't.
      await OvaCareAdminAPI.systemHealth();
      location.hash = "#/users";
      router();
    } catch (err) {
      if (err.status === 403) {
        OvaCareAdminAPI.clearTokens();
        errorEl.innerHTML = `<div class="banner danger">Signed in, but this account does not have admin access.</div>`;
      } else {
        errorEl.innerHTML = `<div class="banner danger">${escapeHtml(err.message)}</div>`;
      }
    }
  });
}

async function viewUsers() {
  mount(`<h1>Users</h1>${RESTRICTED_NOTE}<div id="users-body"><p class="muted">Loading…</p></div>`);
  try {
    const users = await OvaCareAdminAPI.listUsers();
    document.getElementById("users-body").innerHTML = `
      <div class="card">
        <table>
          <thead><tr><th>Email</th><th>Role</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>
            ${users.map((u) => `
              <tr>
                <td>${escapeHtml(u.email)}</td>
                <td>${escapeHtml(u.role)}</td>
                <td><span class="pill ${u.is_active ? "active" : "inactive"}">${u.is_active ? "Active" : "Inactive"}</span></td>
                <td>${escapeHtml(new Date(u.created_at).toLocaleDateString())}</td>
              </tr>
            `).join("") || `<tr><td colspan="4" class="muted">No users found.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    document.getElementById("users-body").innerHTML = bannerFor(err);
  }
}

async function viewModels() {
  mount(`<h1>Model Versions</h1><p class="muted">Full lifecycle history — development, validation, staging, production, and archived
    artifacts (requirement #77). Production is promoted manually; nothing here auto-replaces it.</p>
    <div id="models-body"><p class="muted">Loading…</p></div>`);
  try {
    const models = await OvaCareAdminAPI.listModels();
    document.getElementById("models-body").innerHTML = `
      <div class="card">
        <table>
          <thead><tr><th>Model</th><th>Version</th><th>Stage</th><th>Calibration</th><th>Dataset version</th><th>Review status</th><th>Trained</th><th>Promoted</th></tr></thead>
          <tbody>
            ${models.map((m) => `
              <tr>
                <td>${escapeHtml(m.model_name)}</td>
                <td>${escapeHtml(m.model_version)}</td>
                <td><span class="pill ${escapeHtml(m.stage)}">${escapeHtml(m.stage)}</span></td>
                <td>${escapeHtml(m.calibration_method || "—")}</td>
                <td>${escapeHtml(m.dataset_version || "—")}</td>
                <td>${escapeHtml(m.review_status)}</td>
                <td>${escapeHtml(new Date(m.training_date).toLocaleDateString())}</td>
                <td>${m.promoted_at ? escapeHtml(new Date(m.promoted_at).toLocaleDateString()) : "—"}</td>
              </tr>
            `).join("") || `<tr><td colspan="8" class="muted">No model versions recorded yet.</td></tr>`}
          </tbody>
        </table>
      </div>
      ${models.length ? `
        <div class="card">
          <h2>Evaluation metrics</h2>
          <p class="muted">Raw metrics payload per version, as recorded at training/validation time.</p>
          ${models.map((m) => `
            <details style="margin-bottom: 10px;">
              <summary>${escapeHtml(m.model_name)} · ${escapeHtml(m.model_version)}</summary>
              <pre style="white-space: pre-wrap; font-size: 0.8rem; background: var(--color-bg); padding: 12px; border-radius: var(--radius-sm);">${escapeHtml(JSON.stringify(m.evaluation_metrics, null, 2))}</pre>
            </details>
          `).join("")}
        </div>
      ` : ""}
    `;
  } catch (err) {
    document.getElementById("models-body").innerHTML = bannerFor(err);
  }
}

async function viewSystemHealth() {
  mount(`<h1>System Health</h1><div id="health-body"><p class="muted">Loading…</p></div>`);
  try {
    const h = await OvaCareAdminAPI.systemHealth();
    document.getElementById("health-body").innerHTML = `
      <div class="card-grid">
        <div class="card stat">
          <span class="label">Database</span>
          <span class="value" style="color: ${h.database_reachable ? "var(--color-success)" : "var(--color-danger)"}">
            ${h.database_reachable ? "Reachable" : "Unreachable"}
          </span>
        </div>
        <div class="card stat">
          <span class="label">Production model</span>
          <span class="value" style="color: ${h.production_model_loaded ? "var(--color-success)" : "var(--color-warning)"}">
            ${h.production_model_loaded ? "Loaded" : "Not loaded"}
          </span>
          ${h.production_model_version ? `<span class="muted">${escapeHtml(h.production_model_version)}</span>` : ""}
        </div>
        <div class="card stat">
          <span class="label">Total users</span>
          <span class="value">${h.total_users}</span>
        </div>
        <div class="card stat">
          <span class="label">Total assessments</span>
          <span class="value">${h.total_assessments}</span>
        </div>
        <div class="card stat">
          <span class="label">Total predictions</span>
          <span class="value">${h.total_predictions}</span>
        </div>
      </div>
      ${!h.production_model_loaded ? `
        <div class="banner warning">No production model is currently loaded. Any assessment submitted right now will
          correctly receive an <code>insufficient_data</code> screening outcome rather than a fabricated prediction —
          this is the intended fail-safe behavior (see docs/clinical_safety.md), not a bug to work around by forcing a
          result.</div>
      ` : ""}
      <p class="muted">Checked at ${escapeHtml(new Date(h.checked_at).toLocaleString())}. This reflects live backend/database
        state, not a cached or simulated value.</p>
    `;
  } catch (err) {
    document.getElementById("health-body").innerHTML = bannerFor(err);
  }
}

async function viewAuditLogs() {
  mount(`<h1>Audit Logs</h1><p class="muted">Immutable event log. By design (docs/security.md), entries record who did
    what to which record and when — never the sensitive payload itself.</p>
    <div id="audit-body"><p class="muted">Loading…</p></div>`);
  try {
    const logs = await OvaCareAdminAPI.auditLogs();
    document.getElementById("audit-body").innerHTML = `
      <div class="card">
        <table>
          <thead><tr><th>Time</th><th>Actor</th><th>Role</th><th>Action</th><th>Target</th></tr></thead>
          <tbody>
            ${logs.map((l) => `
              <tr>
                <td>${escapeHtml(new Date(l.created_at).toLocaleString())}</td>
                <td>${escapeHtml(l.actor_user_id ?? "—")}</td>
                <td>${escapeHtml(l.actor_role ?? "—")}</td>
                <td>${escapeHtml(l.action)}</td>
                <td>${escapeHtml(l.target_type ?? "—")}${l.target_id ? ` · ${escapeHtml(l.target_id)}` : ""}</td>
              </tr>
            `).join("") || `<tr><td colspan="5" class="muted">No audit events recorded yet.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    document.getElementById("audit-body").innerHTML = bannerFor(err);
  }
}

// ---------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------

async function viewMonitoring() {
  mount(`<h1>ML Monitoring</h1>
    <p class="muted">Prediction distribution, missing-data rate, model-version breakdown, inference errors/latency,
      and a drift signal — all computed fresh from real rows, over a rolling window. No model is retrained or
      replaced automatically from anything on this page (requirement #39/#77).</p>
    <div id="monitoring-body"><p class="muted">Loading…</p></div>`);
  try {
    const m = await OvaCareAdminAPI.monitoring(30);
    const dist = m.prediction_distribution;
    const drift = m.drift;
    document.getElementById("monitoring-body").innerHTML = `
      <p class="muted">Window: last ${m.window_days} days · generated ${escapeHtml(new Date(m.generated_at).toLocaleString())} ·
        production model ${m.production_model_version ? escapeHtml(m.production_model_version) : "none loaded"}</p>

      <div class="card-grid">
        <div class="card stat">
          <span class="label">Predictions in window</span>
          <span class="value">${dist.total_predictions}</span>
        </div>
        <div class="card stat">
          <span class="label">Missing-data rate</span>
          <span class="value">${dist.missing_data_rate_pct != null ? dist.missing_data_rate_pct + "%" : "—"}</span>
        </div>
        <div class="card stat">
          <span class="label">Model-unavailable rate</span>
          <span class="value">${dist.model_unavailable_rate_pct != null ? dist.model_unavailable_rate_pct + "%" : "—"}</span>
        </div>
        <div class="card stat">
          <span class="label">Assessment field-gap rate</span>
          <span class="value">${m.assessment_missing_field_rate_pct != null ? m.assessment_missing_field_rate_pct + "%" : "—"}</span>
        </div>
      </div>

      <div class="card">
        <h2>Outcome distribution</h2>
        ${
          dist.total_predictions
            ? `<table><thead><tr><th>Outcome</th><th>Count</th><th>%</th></tr></thead><tbody>
                ${Object.entries(dist.outcome_distribution).map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${v}</td><td>${dist.outcome_distribution_pct[k]}%</td></tr>`).join("")}
              </tbody></table>`
            : `<p class="muted">No predictions in this window.</p>`
        }
      </div>

      <div class="card">
        <h2>Model version breakdown</h2>
        ${
          dist.total_predictions
            ? `<table><tbody>${Object.entries(dist.model_version_distribution).map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${v}</td></tr>`).join("")}</tbody></table>`
            : `<p class="muted">No predictions in this window.</p>`
        }
      </div>

      <div class="card">
        <h2>Drift signal</h2>
        ${
          drift.available
            ? `<p>Training-time positive rate: <strong>${(drift.baseline_positive_rate * 100).toFixed(1)}%</strong> ·
                Current window positive rate: <strong>${(drift.current_positive_rate * 100).toFixed(1)}%</strong>
                (${drift.n_decided_predictions} decided predictions)</p>
               <p>Population stability index: <strong>${drift.population_stability_index}</strong>
                ${drift.notable_drift ? `<span class="pill danger">notable — review recommended</span>` : `<span class="pill">within normal range</span>`}</p>
               <p class="muted">${escapeHtml(drift.note)}</p>`
            : `<p class="muted">${escapeHtml(drift.reason)}</p>`
        }
      </div>

      <div class="card">
        <h2>Inference errors &amp; latency</h2>
        <p>Errors since process start: <strong>${m.inference_errors.count_since_process_start}</strong></p>
        <p class="muted">${escapeHtml(m.inference_errors.note)}</p>
        ${
          m.inference_latency.n_samples
            ? `<p>Latency — p50: <strong>${m.inference_latency.p50_ms}ms</strong> · p95: <strong>${m.inference_latency.p95_ms}ms</strong> (${m.inference_latency.n_samples} samples)</p>`
            : `<p class="muted">No inference latency samples recorded yet.</p>`
        }
      </div>
    `;
  } catch (err) {
    document.getElementById("monitoring-body").innerHTML = bannerFor(err);
  }
}

const ADMIN_ROUTES = {
  "#/login": { view: viewLogin, public: true },
  "#/users": { view: viewUsers, public: false },
  "#/models": { view: viewModels, public: false },
  "#/monitoring": { view: viewMonitoring, public: false },
  "#/system-health": { view: viewSystemHealth, public: false },
  "#/audit-logs": { view: viewAuditLogs, public: false },
};

function router() {
  let hash = location.hash || (OvaCareAdminAPI.isAuthenticated() ? "#/users" : "#/login");
  if (!ADMIN_ROUTES[hash]) hash = OvaCareAdminAPI.isAuthenticated() ? "#/users" : "#/login";

  const route = ADMIN_ROUTES[hash];
  if (!route.public && !OvaCareAdminAPI.isAuthenticated()) {
    location.hash = "#/login";
    return;
  }
  if (route.public && OvaCareAdminAPI.isAuthenticated() && hash === "#/login") {
    location.hash = "#/users";
    return;
  }

  if (route.public) {
    document.getElementById("app").innerHTML = `<main class="content" style="max-width: 480px; margin: 0 auto;" id="view"></main>`;
    route.view();
    return;
  }

  renderShell();
  setActiveNav(hash);
  route.view();
}

window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", router);
