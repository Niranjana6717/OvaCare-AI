// OvaCare AI — web app shell: hash router + view renderers.
// No framework, no build step (see docs/deployment.md). Views are template
// strings rendered into #view; each render function wires up its own
// event listeners after insertion.

const NAV_ITEMS = [
  { hash: "#/dashboard", label: "Dashboard", icon: "🏠" },
  { hash: "#/assessment", label: "Assessment", icon: "🩺" },
  { hash: "#/cycles", label: "Period Tracker", icon: "🗓️" },
  { hash: "#/symptoms", label: "Symptoms", icon: "📝" },
  { hash: "#/history", label: "History", icon: "📜" },
  { hash: "#/insights", label: "Insights", icon: "💡" },
  { hash: "#/profile", label: "Profile", icon: "👤" },
  { hash: "#/settings", label: "Settings", icon: "⚙️" },
];

const MEDICAL_DISCLAIMER_SHORT =
  "OvaCare's AI screening is informational only and does not diagnose PCOS or any other medical condition. " +
  "A healthcare professional should evaluate persistent or concerning symptoms.";

// Current consent copy/policy/app version stamped on every consent record
// this client submits. Bump CONSENT_META.consent_version (and re-collect
// consent) if the wording in CONSENT_CATALOG below materially changes.
const CONSENT_META = { consent_version: "1.0.0", policy_version: "1.0.0", app_version: "0.1.0" };

// The six consent categories the backend supports (app.database.models.consent.ConsentType).
// Plain-language copy, no legal jargon — shown at registration (required
// types only) and in Settings (all six, with grant/withdraw for optional
// ones). Keep this in sync with apps/mobile/lib/screens/consent_screen.dart
// and settings_screen.dart's consent copy.
const CONSENT_CATALOG = [
  {
    type: "core_service",
    label: "Service usage",
    description: "Creating your account and keeping the app working and secure. Required to use OvaCare.",
    required: true,
  },
  {
    type: "health_data_processing",
    label: "Health-data processing",
    description:
      "Storing the cycle, symptom, and assessment information you enter so OvaCare can track your health over time. Required to use OvaCare's core features.",
    required: true,
  },
  {
    type: "ai_screening_acknowledgement",
    label: "AI screening",
    description:
      "Using an AI model to screen your assessment answers for patterns associated with PCOS. This is a screening tool, not a diagnosis. You can withdraw this and still use cycle and symptom tracking — you just won't be able to request new AI screening results.",
    required: false,
  },
  {
    type: "notification_permission",
    label: "Notifications",
    description: "Sending you period and cycle reminder notifications, at the schedule and privacy level you choose below.",
    required: false,
  },
  {
    type: "analytics",
    label: "Analytics",
    description: "Collecting anonymized usage analytics (which screens are used, not your health responses) to help us improve the app.",
    required: false,
  },
  {
    type: "research_model_improvement",
    label: "Research & model improvement",
    description: "Allowing your de-identified assessment data to be used to improve the accuracy of future versions of the screening model.",
    required: false,
  },
];

function activeConsentMap(consents) {
  const active = {};
  for (const c of consents) {
    if (c.accepted && !c.withdrawn_at) active[c.consent_type] = c;
  }
  return active;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

function renderShell() {
  const app = document.getElementById("app");
  const authed = OvaCareAPI.isAuthenticated();
  if (!authed) {
    app.innerHTML = `<main class="content" style="max-width:100%;margin:0 auto;"><div id="view"></div></main>`;
    return;
  }
  app.innerHTML = `
    <nav class="sidebar">
      <div class="brand">OvaCare AI</div>
      ${NAV_ITEMS.map(
        (item) => `<a class="nav-link" data-hash="${item.hash}" href="${item.hash}">${item.icon} ${item.label}</a>`
      ).join("")}
      <a class="nav-link" id="logout-link" href="#" style="margin-top:auto;">🚪 Log out</a>
    </nav>
    <main class="content"><div id="view"></div></main>
  `;
  document.getElementById("logout-link").addEventListener("click", async (e) => {
    e.preventDefault();
    await OvaCareAPI.logout().catch(() => {});
    location.hash = "#/login";
  });
}

function setActiveNav(hash) {
  document.querySelectorAll(".nav-link[data-hash]").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-hash") === hash);
  });
}

function mount(html) {
  document.getElementById("view").innerHTML = html;
}

function bannerFor(err) {
  return `<div class="banner danger">${escapeHtml(err.message || "Something went wrong. Please try again.")}</div>`;
}

// ---------------------------------------------------------------------
// Auth views
// ---------------------------------------------------------------------

function viewLogin() {
  mount(`
    <div class="auth-shell">
      <div class="card">
        <h2>Welcome back</h2>
        <div id="form-error"></div>
        <form id="login-form">
          <label for="email">Email</label>
          <input id="email" type="email" required>
          <label for="password">Password</label>
          <input id="password" type="password" required>
          <div style="margin-top:20px;display:flex;gap:10px;">
            <button class="btn" type="submit">Log in</button>
            <a class="btn secondary" href="#/register">Create account</a>
          </div>
        </form>
      </div>
    </div>
  `);
  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await OvaCareAPI.login(document.getElementById("email").value, document.getElementById("password").value);
      location.hash = "#/dashboard";
      renderShell();
      router();
    } catch (err) {
      document.getElementById("form-error").innerHTML = bannerFor(err);
    }
  });
}

function viewRegister() {
  mount(`
    <div class="auth-shell">
      <div class="card">
        <h2>Create your OvaCare account</h2>
        <p class="muted" style="font-size:0.85rem;">At least 10 characters, with both letters and numbers.</p>
        <div id="form-error"></div>
        <form id="register-form">
          <label for="email">Email</label>
          <input id="email" type="email" required>
          <label for="password">Password</label>
          <input id="password" type="password" required minlength="10">
          <div style="margin-top:20px;display:flex;gap:10px;">
            <button class="btn" type="submit">Create account</button>
            <a class="btn secondary" href="#/login">Back to login</a>
          </div>
        </form>
      </div>
    </div>
  `);
  document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await OvaCareAPI.register(document.getElementById("email").value, document.getElementById("password").value);
      location.hash = "#/consent";
      renderShell();
      router();
    } catch (err) {
      document.getElementById("form-error").innerHTML = bannerFor(err);
    }
  });
}

// ---------------------------------------------------------------------
// Consent (requirement #57)
// ---------------------------------------------------------------------

function viewConsent() {
  mount(`
    <div class="auth-shell" style="max-width:480px;">
      <div class="card">
        <h2>Before You Continue</h2>
        <p>OvaCare collects health information to provide period tracking, symptom tracking, and AI-assisted screening features.</p>
        <p>Some questions are optional.</p>
        <p><strong>Your screening result is not a medical diagnosis and should not replace professional medical advice.</strong></p>
        <p>You can review our Privacy Policy and manage your data settings at any time.</p>
        <div id="form-error"></div>
        <form id="consent-form">
          <label style="display:flex;align-items:center;gap:8px;margin-top:16px;">
            <input type="checkbox" id="agree" style="width:auto;" required>
            <span style="font-size:0.9rem;">I understand how my information will be used.</span>
          </label>
          <button class="btn" type="submit" style="margin-top:18px;">Continue</button>
        </form>
      </div>
    </div>
  `);
  document.getElementById("consent-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      for (const consent_type of ["core_service", "health_data_processing"]) {
        await OvaCareAPI.submitConsent({ consent_type, accepted: true, ...CONSENT_META });
      }
      location.hash = "#/dashboard";
      renderShell();
      router();
    } catch (err) {
      document.getElementById("form-error").innerHTML = bannerFor(err);
    }
  });
}

// ---------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------

async function viewDashboard() {
  mount(`<p class="muted">Loading…</p>`);
  try {
    const [summary, estimate, insights] = await Promise.all([
      OvaCareAPI.cycleSummary(),
      OvaCareAPI.cycleEstimate(),
      OvaCareAPI.getInsights(),
    ]);

    mount(`
      <h1>Dashboard</h1>
      <div class="card-grid">
        <div class="card stat">
          <div class="label">Average cycle length</div>
          <div class="value">${summary.sufficient_data ? summary.average_cycle_length_days + " days" : "—"}</div>
          ${!summary.sufficient_data ? `<div class="muted" style="font-size:0.85rem;">${escapeHtml(summary.message)}</div>` : ""}
        </div>
        <div class="card stat">
          <div class="label">${escapeHtml(estimate.label)}</div>
          <div class="value">${estimate.sufficient_data ? escapeHtml(estimate.estimated_start_date) : "—"}</div>
          ${!estimate.sufficient_data ? `<div class="muted" style="font-size:0.85rem;">${escapeHtml(estimate.message)}</div>` : ""}
        </div>
        <div class="card stat">
          <div class="label">Symptoms logged (90 days)</div>
          <div class="value">${insights.symptom_trends.total_logged}</div>
        </div>
      </div>

      <div class="card">
        <h2>Quick actions</h2>
        <div class="quick-actions">
          <a class="btn" href="#/assessment">New Assessment</a>
          <a class="btn secondary" href="#/cycles">Log Period</a>
          <a class="btn secondary" href="#/symptoms">Log Symptom</a>
        </div>
      </div>

      <div class="card">
        <h2>Educational note</h2>
        ${insights.educational_content
          .map((item) => `<p><strong>${escapeHtml(item.title)}</strong><br>${escapeHtml(item.body)}</p>`)
          .join("")}
        <p class="muted" style="font-size:0.78rem;">Non-diagnostic, review status: ${escapeHtml(insights.educational_content[0]?.review_status || "n/a")}</p>
      </div>
    `);
  } catch (err) {
    mount(bannerFor(err));
  }
}

// ---------------------------------------------------------------------
// Cycles / period tracker
// ---------------------------------------------------------------------

async function viewCycles() {
  mount(`<p class="muted">Loading…</p>`);
  try {
    const [cycles, summary, estimate] = await Promise.all([
      OvaCareAPI.listCycles(),
      OvaCareAPI.cycleSummary(),
      OvaCareAPI.cycleEstimate(),
    ]);

    mount(`
      <h1>Period Tracker</h1>

      <div class="card-grid">
        <div class="card stat">
          <div class="label">${escapeHtml(estimate.label)}</div>
          <div class="value">${estimate.sufficient_data ? escapeHtml(estimate.estimated_start_date) : "—"}</div>
          ${!estimate.sufficient_data ? `<div class="banner info" style="margin-top:10px;">${escapeHtml(estimate.message)}</div>` : ""}
        </div>
        <div class="card stat">
          <div class="label">Average cycle length</div>
          <div class="value">${summary.sufficient_data ? summary.average_cycle_length_days + " days" : "—"}</div>
        </div>
        <div class="card stat">
          <div class="label">Cycle variability</div>
          <div class="value">${summary.sufficient_data ? "±" + summary.cycle_variability_stdev_days + " days" : "—"}</div>
          ${summary.is_high_variability ? `<div class="banner warning" style="margin-top:10px;">Your recent cycle lengths have varied. Continue tracking your cycles, and consider discussing persistent changes with a qualified healthcare professional.</div>` : ""}
        </div>
      </div>

      <div class="card">
        <h2>Log a period</h2>
        <div id="form-error"></div>
        <form id="cycle-form">
          <div style="display:flex;gap:16px;flex-wrap:wrap;">
            <div style="flex:1;min-width:160px;"><label>Start date</label><input type="date" id="start_date" required></div>
            <div style="flex:1;min-width:160px;"><label>End date</label><input type="date" id="end_date"></div>
            <div style="flex:1;min-width:160px;">
              <label>Flow</label>
              <select id="flow_level"><option value="">—</option><option>spotting</option><option>light</option><option>medium</option><option>heavy</option></select>
            </div>
          </div>
          <label>Notes</label>
          <textarea id="notes" rows="2"></textarea>
          <button class="btn" type="submit" style="margin-top:14px;">Save period</button>
        </form>
      </div>

      <div class="card">
        <h2>Cycle history</h2>
        <table>
          <thead><tr><th>Start</th><th>End</th><th>Cycle length</th><th>Duration</th><th></th></tr></thead>
          <tbody>
            ${cycles
              .map(
                (c) => `<tr>
                  <td>${escapeHtml(c.start_date)}</td>
                  <td>${escapeHtml(c.end_date || "—")}</td>
                  <td>${c.cycle_length_days != null ? c.cycle_length_days + "d" : "—"}</td>
                  <td>${c.period_duration_days != null ? c.period_duration_days + "d" : "—"}</td>
                  <td><a href="#" data-delete="${c.id}" class="muted">Delete</a></td>
                </tr>`
              )
              .join("") || `<tr><td colspan="5" class="muted">No periods logged yet.</td></tr>`}
          </tbody>
        </table>
      </div>
    `);

    document.getElementById("cycle-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await OvaCareAPI.createCycle({
          start_date: document.getElementById("start_date").value,
          end_date: document.getElementById("end_date").value || null,
          flow_level: document.getElementById("flow_level").value || null,
          notes: document.getElementById("notes").value || null,
        });
        viewCycles();
      } catch (err) {
        document.getElementById("form-error").innerHTML = bannerFor(err);
      }
    });

    document.querySelectorAll("[data-delete]").forEach((el) =>
      el.addEventListener("click", async (e) => {
        e.preventDefault();
        await OvaCareAPI.deleteCycle(el.getAttribute("data-delete"));
        viewCycles();
      })
    );
  } catch (err) {
    mount(bannerFor(err));
  }
}

// ---------------------------------------------------------------------
// Symptoms
// ---------------------------------------------------------------------

const SYMPTOM_TYPES = ["acne", "hair_growth_changes", "hair_loss", "pelvic_discomfort", "fatigue", "mood_changes", "other"];

async function viewSymptoms() {
  mount(`<p class="muted">Loading…</p>`);
  try {
    const symptoms = await OvaCareAPI.listSymptoms();
    mount(`
      <h1>Symptoms</h1>
      <div class="card">
        <h2>Log a symptom</h2>
        <div id="form-error"></div>
        <form id="symptom-form">
          <div style="display:flex;gap:16px;flex-wrap:wrap;">
            <div style="flex:1;min-width:160px;">
              <label>Symptom</label>
              <select id="symptom_type">${SYMPTOM_TYPES.map((t) => `<option value="${t}">${t.replace(/_/g, " ")}</option>`).join("")}</select>
            </div>
            <div style="flex:1;min-width:160px;"><label>Severity (1–5)</label><input type="number" id="severity" min="1" max="5" value="2" required></div>
            <div style="flex:1;min-width:160px;"><label>Date</label><input type="date" id="logged_date" required></div>
          </div>
          <label>Notes</label>
          <textarea id="notes" rows="2"></textarea>
          <button class="btn" type="submit" style="margin-top:14px;">Save symptom</button>
        </form>
      </div>
      <div class="card">
        <h2>Symptom history</h2>
        <table>
          <thead><tr><th>Date</th><th>Symptom</th><th>Severity</th><th></th></tr></thead>
          <tbody>
            ${symptoms
              .map(
                (s) => `<tr>
                  <td>${escapeHtml(s.logged_date)}</td>
                  <td>${escapeHtml(s.symptom_type.replace(/_/g, " "))}</td>
                  <td>${s.severity}/5</td>
                  <td><a href="#" data-delete="${s.id}" class="muted">Delete</a></td>
                </tr>`
              )
              .join("") || `<tr><td colspan="4" class="muted">No symptoms logged yet.</td></tr>`}
          </tbody>
        </table>
      </div>
    `);
    document.getElementById("symptom-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await OvaCareAPI.createSymptom({
          symptom_type: document.getElementById("symptom_type").value,
          severity: Number(document.getElementById("severity").value),
          logged_date: document.getElementById("logged_date").value,
          notes: document.getElementById("notes").value || null,
        });
        viewSymptoms();
      } catch (err) {
        document.getElementById("form-error").innerHTML = bannerFor(err);
      }
    });
    document.querySelectorAll("[data-delete]").forEach((el) =>
      el.addEventListener("click", async (e) => {
        e.preventDefault();
        await OvaCareAPI.deleteSymptom(el.getAttribute("data-delete"));
        viewSymptoms();
      })
    );
  } catch (err) {
    mount(bannerFor(err));
  }
}

// ---------------------------------------------------------------------
// Assessment: questionnaire -> review -> result (requirement #75)
// ---------------------------------------------------------------------

// Hand-synced from ml-platform/src/feature_schema.py's FEATURES list (see
// that file's docstring for full sourcing/citations). REQUIRED_FIELDS must
// all be answered or app.ml.preprocessing returns insufficient_data — this
// list was previously incomplete here (missing bmi/hair_thinning/
// skin_darkening/weight_gain), which meant every real submission through
// this form was guaranteed to come back insufficient_data regardless of
// what the person actually entered. Fixed to match the real schema.
const REQUIRED_ASSESSMENT_FIELDS = [
  { id: "age", label: "Age", type: "number", min: 10, max: 60 },
  { id: "bmi", label: "BMI", type: "number", min: 10, max: 60 },
  { id: "cycle_regularity", label: "Cycle regularity", type: "select", options: ["regular", "irregular"] },
  { id: "average_cycle_length_days", label: "Average cycle length (days)", type: "number", min: 10, max: 90 },
  { id: "acne", label: "Acne", type: "select", options: ["no", "yes"] },
  { id: "hair_growth_excess", label: "Excess hair growth", type: "select", options: ["no", "yes"] },
  { id: "hair_thinning", label: "Hair thinning / hair loss", type: "select", options: ["no", "yes"] },
  { id: "skin_darkening", label: "Skin darkening", type: "select", options: ["no", "yes"] },
  { id: "weight_gain", label: "Recent weight gain", type: "select", options: ["no", "yes"] },
];

// Optional: present in the source dataset, but a person may not have
// these results — missing values don't block a screening result
// (requirement #74, "I don't have these results").
const OPTIONAL_ASSESSMENT_FIELDS = [
  { id: "fsh", label: "FSH (mIU/mL)", type: "number", step: "0.1" },
  { id: "lh", label: "LH (mIU/mL)", type: "number", step: "0.1" },
  { id: "amh", label: "AMH (ng/mL)", type: "number", step: "0.1" },
  { id: "prolactin", label: "Prolactin (ng/mL)", type: "number", step: "0.1" },
  { id: "tsh", label: "TSH (mIU/L)", type: "number", step: "0.1" },
];

function viewAssessment() {
  const requiredRows = REQUIRED_ASSESSMENT_FIELDS.map((f) =>
    f.type === "select"
      ? `<label>${f.label}</label><select id="${f.id}" required>${f.options
          .map((o) => `<option value="${o}">${o[0].toUpperCase() + o.slice(1)}</option>`)
          .join("")}</select>`
      : `<label>${f.label}</label><input type="number" id="${f.id}" min="${f.min}" max="${f.max}" required>`
  ).join("");

  const optionalRows = OPTIONAL_ASSESSMENT_FIELDS.map(
    (f) => `
      <label style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
        <span>${f.label}</span>
      </label>
      <div style="display:flex;gap:8px;align-items:center;">
        <input type="number" step="${f.step}" id="${f.id}" style="flex:1;">
        <label style="display:flex;align-items:center;gap:6px;font-size:0.8rem;white-space:nowrap;">
          <input type="checkbox" id="${f.id}_skip" style="width:auto;" onchange="document.getElementById('${f.id}').disabled=this.checked;"> Don't have this
        </label>
      </div>`
  ).join("");

  mount(`
    <h1>AI-Assisted PCOS Screening</h1>
    <div class="banner info">${MEDICAL_DISCLAIMER_SHORT}</div>
    <div class="card">
      <h2>Tell us about your cycle and symptoms</h2>
      <div id="form-error"></div>
      <form id="assessment-form">
        ${requiredRows}
        <hr style="border:none;border-top:1px solid var(--color-border);margin:20px 0;">
        <p class="muted" style="font-size:0.85rem;">Optional — leave blank or mark "Don't have this" if you don't have these results.</p>
        ${optionalRows}
        <hr style="border:none;border-top:1px solid var(--color-border);margin:20px 0;">
        <p class="muted" style="font-size:0.85rem;">If any of these apply, we'll show you information about seeking urgent care. This check runs independently of the screening above and never delays or requires completing it.</p>
        <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="soaking_through_protection_hourly" style="width:auto;"> Soaking through pad/tampon protection hourly</label>
        <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="bleeding_with_dizziness_or_fainting" style="width:auto;"> Heavy bleeding with dizziness or fainting</label>
        <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="fainting_or_severe_dizziness" style="width:auto;"> Fainting or severe dizziness</label>
        <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="chest_pain_or_breathing_difficulty" style="width:auto;"> Chest pain or difficulty breathing</label>
        <label>Pelvic pain severity (optional, 1–5)</label>
        <input type="number" id="pelvic_pain_severity" min="1" max="5">
        <button class="btn" type="submit" style="margin-top:18px;">Review my answers</button>
      </form>
    </div>
  `);
  document.getElementById("assessment-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const responses = {};
    for (const f of REQUIRED_ASSESSMENT_FIELDS) {
      const el = document.getElementById(f.id);
      responses[f.id] = f.type === "number" ? Number(el.value) : el.value;
    }
    for (const f of OPTIONAL_ASSESSMENT_FIELDS) {
      const skipped = document.getElementById(`${f.id}_skip`).checked;
      const raw = document.getElementById(f.id).value;
      responses[f.id] = !skipped && raw ? Number(raw) : null;
    }
    const pelvicPainRaw = document.getElementById("pelvic_pain_severity").value;
    const safetyFields = {
      soaking_through_protection_hourly: document.getElementById("soaking_through_protection_hourly").checked,
      bleeding_with_dizziness_or_fainting: document.getElementById("bleeding_with_dizziness_or_fainting").checked,
      fainting_or_severe_dizziness: document.getElementById("fainting_or_severe_dizziness").checked,
      chest_pain_or_breathing_difficulty: document.getElementById("chest_pain_or_breathing_difficulty").checked,
      pelvic_pain_severity: pelvicPainRaw ? Number(pelvicPainRaw) : null,
    };
    viewAssessmentReview(responses, safetyFields);
  });
}

function viewAssessmentReview(responses, safetyFields) {
  const rows = Object.entries(responses)
    .map(([k, v]) => `<tr><td>${escapeHtml(k.replace(/_/g, " "))}</td><td>${v === null ? "Not provided" : escapeHtml(v)}</td></tr>`)
    .join("");
  mount(`
    <h1>Review Your Information</h1>
    <div class="card">
      <table><tbody>${rows}</tbody></table>
      <p class="muted" style="font-size:0.85rem;margin-top:14px;">This result will be based only on the information you provided above.</p>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;">
        <button class="btn secondary" id="edit-btn">Edit Information</button>
        <button class="btn" id="submit-btn">Submit Assessment</button>
      </div>
      <div id="form-error"></div>
    </div>
  `);
  document.getElementById("edit-btn").addEventListener("click", viewAssessment);
  document.getElementById("submit-btn").addEventListener("click", async () => {
    try {
      const created = await OvaCareAPI.submitAssessment({
        responses,
        unanswered_fields: Object.entries(responses)
          .filter(([, v]) => v === null)
          .map(([k]) => k),
        ...safetyFields,
      });
      const consents = await OvaCareAPI.getConsents();
      const hasAiScreeningConsent = Object.prototype.hasOwnProperty.call(
        activeConsentMap(consents),
        "ai_screening_acknowledgement"
      );
      if (!hasAiScreeningConsent) {
        viewAiScreeningConsent(created.assessment_id);
        return;
      }
      const prediction = await OvaCareAPI.requestPrediction(created.assessment_id);
      viewAssessmentResult(prediction);
    } catch (err) {
      document.getElementById("form-error").innerHTML = bannerFor(err);
    }
  });
}

// Requirement: consent BEFORE AI screening. The assessment answers are
// already saved at this point (POST /assessments above) — this screen only
// gates the separate POST /predictions call, matching the backend's own
// AI_SCREENING_ACKNOWLEDGEMENT check in app/api/predictions.py. Declining
// leaves the assessment saved with no prediction; the user can return to
// it (or submit a new one) once they consent.
function viewAiScreeningConsent(assessmentId) {
  const copy = CONSENT_CATALOG.find((c) => c.type === "ai_screening_acknowledgement");
  mount(`
    <div class="auth-shell" style="max-width:480px;">
      <div class="card">
        <h2>Before We Show Your Result</h2>
        <p>${escapeHtml(copy.description)}</p>
        <p class="muted" style="font-size:0.85rem;">You can withdraw this at any time from Settings.</p>
        <div id="form-error"></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;">
          <button class="btn secondary" id="ai-consent-decline">Not now</button>
          <button class="btn" id="ai-consent-agree">I understand, show my result</button>
        </div>
      </div>
    </div>
  `);
  document.getElementById("ai-consent-decline").addEventListener("click", () => {
    mount(`
      <h1>Assessment Saved</h1>
      <div class="card">
        <p>Your answers were saved. When you're ready for your AI screening result, accept AI-screening consent from your assessment history or Settings.</p>
        <a class="btn secondary" href="#/dashboard">Back to dashboard</a>
      </div>
    `);
  });
  document.getElementById("ai-consent-agree").addEventListener("click", async () => {
    try {
      await OvaCareAPI.submitConsent({ consent_type: "ai_screening_acknowledgement", accepted: true, ...CONSENT_META });
      const prediction = await OvaCareAPI.requestPrediction(assessmentId);
      viewAssessmentResult(prediction);
    } catch (err) {
      document.getElementById("form-error").innerHTML = bannerFor(err);
    }
  });
}

function viewAssessmentResult(prediction) {
  const { safety, result } = prediction;
  const factorsHtml = (result.explanation.factors || [])
    .map((f) => `<li><strong>${escapeHtml(f.label)}</strong> — ${escapeHtml(f.why_it_matters)}</li>`)
    .join("");

  mount(`
    <h1>Your Screening Result</h1>
    ${safety.urgent ? `<div class="banner danger">${escapeHtml(safety.message)}</div>` : ""}
    <div class="card">
      <h2>Screening indication</h2>
      <p style="font-size:1.05rem;">${escapeHtml(result.message)}</p>
      ${result.probability != null ? `<p class="muted">Model probability: ${(result.probability * 100).toFixed(0)}%</p>` : ""}

      ${
        factorsHtml
          ? `<h3>Factors that contributed</h3><ul>${factorsHtml}</ul><p class="muted" style="font-size:0.85rem;">${escapeHtml(result.explanation_framing || "")}</p>`
          : ""
      }

      <p class="muted" style="font-size:0.85rem;">Assessed ${escapeHtml(result.assessed_at)} · model ${escapeHtml(result.model_version)}</p>
      <div class="disclaimer">${escapeHtml(result.medical_disclaimer)}</div>
    </div>
    <a class="btn secondary" href="#/dashboard">Back to dashboard</a>
  `);
}

// ---------------------------------------------------------------------
// History
// ---------------------------------------------------------------------

async function viewHistory() {
  mount(`<p class="muted">Loading…</p>`);
  try {
    const history = await OvaCareAPI.predictionHistory();
    mount(`
      <h1>Assessment History</h1>
      ${
        history
          .map(
            (r) => `<div class="card">
              <p class="muted" style="font-size:0.85rem;">${escapeHtml(r.assessed_at)} · model ${escapeHtml(r.model_version)}</p>
              <p>${escapeHtml(r.message)}</p>
              ${r.probability != null ? `<p class="muted">Probability: ${(r.probability * 100).toFixed(0)}%</p>` : ""}
            </div>`
          )
          .join("") || `<p class="muted">No assessments yet. <a href="#/assessment">Start one</a>.</p>`
      }
    `);
  } catch (err) {
    mount(bannerFor(err));
  }
}

// ---------------------------------------------------------------------
// Insights
// ---------------------------------------------------------------------

async function viewInsights() {
  mount(`<p class="muted">Loading…</p>`);
  try {
    const insights = await OvaCareAPI.getInsights();
    const freq = Object.entries(insights.symptom_trends.frequency)
      .map(([k, v]) => `<tr><td>${escapeHtml(k.replace(/_/g, " "))}</td><td>${v}</td></tr>`)
      .join("");
    mount(`
      <h1>Insights</h1>
      <div class="card">
        <h2>Cycle trends</h2>
        ${
          insights.cycle_trends.sufficient_data
            ? `<p>Average cycle length: ${insights.cycle_trends.average_cycle_length_days} days · variability: ±${insights.cycle_trends.cycle_variability_stdev_days} days</p>`
            : `<p class="muted">${escapeHtml(insights.cycle_trends.message)}</p>`
        }
      </div>
      <div class="card">
        <h2>Symptom frequency (90 days)</h2>
        <table><tbody>${freq || '<tr><td class="muted">No symptoms logged yet.</td></tr>'}</tbody></table>
      </div>
      <div class="card">
        <h2>Educational content</h2>
        ${insights.educational_content.map((i) => `<p><strong>${escapeHtml(i.title)}</strong><br>${escapeHtml(i.body)}</p>`).join("")}
      </div>
      <div class="card">
        <h2>Health Report</h2>
        <p class="muted" style="font-size:0.85rem;">Your profile, cycle summary, symptom summary, and most recent AI screening result, with the required disclaimer. Available as JSON or PDF — nothing here is sent anywhere; both download to your device.</p>
        <div id="report-error"></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <button class="btn secondary" id="download-json-btn">Download JSON</button>
          <button class="btn" id="download-pdf-btn">Download PDF</button>
        </div>
      </div>
    `);
    document.getElementById("download-json-btn").addEventListener("click", async () => {
      try {
        const report = await OvaCareAPI.getReport();
        downloadBlob(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }), "ovacare-health-report.json");
      } catch (err) {
        document.getElementById("report-error").innerHTML = bannerFor(err);
      }
    });
    document.getElementById("download-pdf-btn").addEventListener("click", async () => {
      try {
        const blob = await OvaCareAPI.downloadReportPdf();
        downloadBlob(blob, "ovacare-health-report.pdf");
      } catch (err) {
        document.getElementById("report-error").innerHTML = bannerFor(err);
      }
    });
  } catch (err) {
    mount(bannerFor(err));
  }
}

// Triggers a browser "Save As" for an in-memory Blob — used for both report
// downloads above. No file ever leaves the browser except via this save.
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------
// Profile / settings
// ---------------------------------------------------------------------

async function viewProfile() {
  mount(`<p class="muted">Loading…</p>`);
  try {
    const me = await OvaCareAPI.getMe();
    mount(`
      <h1>Profile</h1>
      <div class="card">
        <div id="form-error"></div>
        <form id="profile-form">
          <label>Email</label><input value="${escapeHtml(me.email)}" disabled>
          <label>Full name</label><input id="full_name" value="${escapeHtml(me.full_name || "")}">
          <label>Height (cm)</label><input type="number" id="height_cm" value="${me.height_cm || ""}">
          <label>Weight (kg)</label><input type="number" id="weight_kg" value="${me.weight_kg || ""}">
          <p class="muted">BMI: ${me.bmi != null ? me.bmi : "—"} (informational only — not the primary factor in your screening result)</p>
          <button class="btn" type="submit" style="margin-top:10px;">Save</button>
        </form>
      </div>
      <div class="card">
        <h2>Delete account</h2>
        <p class="muted" style="font-size:0.85rem;">This deactivates your account and marks your data for deletion.</p>
        <button class="btn danger" id="delete-account-btn">Delete my account</button>
      </div>
    `);
    document.getElementById("profile-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await OvaCareAPI.updateMe({
          full_name: document.getElementById("full_name").value || null,
          height_cm: document.getElementById("height_cm").value ? Number(document.getElementById("height_cm").value) : null,
          weight_kg: document.getElementById("weight_kg").value ? Number(document.getElementById("weight_kg").value) : null,
        });
        viewProfile();
      } catch (err) {
        document.getElementById("form-error").innerHTML = bannerFor(err);
      }
    });
    document.getElementById("delete-account-btn").addEventListener("click", async () => {
      if (!confirm("This will deactivate your account and mark your data for deletion. Continue?")) return;
      await OvaCareAPI.deleteMe();
      OvaCareAPI.clearTokens();
      location.hash = "#/login";
      renderShell();
      router();
    });
  } catch (err) {
    mount(bannerFor(err));
  }
}

// Browser Notification permission (requirement: "Request notification
// permission properly. Handle denied notification permissions
// gracefully."). This is the permission for an OS/lock-screen-style
// browser notification specifically — separate from, and not required
// for, the reminder record OvaCareAPI.updateNotificationPreferences saves,
// which always works and is what the in-app Period Reminder card reflects
// either way. This app has no service worker / push subscription (that
// needs a real push provider — see docs/deployment.md), so a granted
// permission here is what a future push integration would build on, not
// itself a guarantee of a background notification while the tab is closed.
function notificationPermissionStatus() {
  if (!("Notification" in window)) return "unsupported";
  return Notification.permission; // "granted" | "denied" | "default"
}

function notificationPermissionNote(status) {
  switch (status) {
    case "unsupported":
      return "This browser doesn't support notification permission — reminders still show in the app.";
    case "denied":
      return "Browser notifications are blocked. Reminders are still saved and viewable in the app — to also see an OS notification, allow notifications for this site in your browser settings.";
    case "granted":
      return "Browser notifications are allowed.";
    default:
      return "You'll be asked to allow browser notifications when you enable reminders.";
  }
}

async function viewSettings() {
  mount(`<p class="muted">Loading…</p>`);
  try {
    const [prefs, consents] = await Promise.all([OvaCareAPI.getNotificationPreferences(), OvaCareAPI.getConsents()]);
    mount(`
      <h1>Settings</h1>
      <div class="card">
        <h2>Period Reminder</h2>
        <div id="form-error"></div>
        <form id="notif-form">
          <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" id="period_reminders_enabled" style="width:auto;" ${prefs.period_reminders_enabled ? "checked" : ""}> Enable reminders</label>
          <p class="muted" id="notif-permission-note" style="font-size:0.8rem;">${escapeHtml(notificationPermissionNote(notificationPermissionStatus()))}</p>
          <label>Remind me</label>
          <select id="days_before_period">
            ${[1, 2, 3, 5].map((d) => `<option value="${d}" ${prefs.days_before_period === d ? "selected" : ""}>${d} day(s) before</option>`).join("")}
          </select>
          <label>Notification time</label>
          <input type="time" id="notification_time" value="${prefs.notification_time.slice(0, 5)}">
          <label style="display:flex;align-items:center;gap:8px;margin-top:16px;"><input type="checkbox" id="privacy_mode" style="width:auto;" ${prefs.privacy_mode ? "checked" : ""}> Use private notification text</label>
          <button class="btn" type="submit" style="margin-top:14px;">Save</button>
        </form>
      </div>
      <div class="card">
        <h2>Consent</h2>
        <p class="muted" style="font-size:0.85rem;">Service usage and health-data processing are required to use OvaCare and were accepted when you registered. The rest are optional — turn them on or off any time; nothing below affects your ability to track cycles or symptoms.</p>
        ${(() => {
          const active = activeConsentMap(consents);
          return CONSENT_CATALOG.map((c) => {
            const isActive = Object.prototype.hasOwnProperty.call(active, c.type);
            return `
              <label style="display:flex;align-items:flex-start;gap:10px;margin-top:16px;">
                <input type="checkbox" data-consent-toggle="${c.type}" style="width:auto;margin-top:3px;"
                  ${isActive ? "checked" : ""} ${c.required ? "disabled" : ""}>
                <span>
                  <strong>${escapeHtml(c.label)}</strong>${c.required ? ` <span class="muted" style="font-size:0.78rem;">(required — active)</span>` : ""}
                  <br><span class="muted" style="font-size:0.85rem;">${escapeHtml(c.description)}</span>
                </span>
              </label>`;
          }).join("");
        })()}
      </div>
    `);
    document.getElementById("notif-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const enabling = document.getElementById("period_reminders_enabled").checked;
      // Ask for OS-notification permission only when the person is turning
      // reminders on and the browser hasn't been asked yet ("default").
      // A "denied" or "unsupported" result is handled gracefully below —
      // the preference is still saved either way, since the in-app
      // reminder itself never depends on this permission.
      if (enabling && notificationPermissionStatus() === "default") {
        try {
          await Notification.requestPermission();
        } catch {
          // Some browsers/environments (e.g. insecure context) throw
          // rather than resolve "denied" — treat the same as denied.
        }
      }
      try {
        await OvaCareAPI.updateNotificationPreferences({
          period_reminders_enabled: enabling,
          days_before_period: Number(document.getElementById("days_before_period").value),
          notification_time: document.getElementById("notification_time").value + ":00",
          cycle_reminders_enabled: prefs.cycle_reminders_enabled,
          symptom_reminders_enabled: prefs.symptom_reminders_enabled,
          privacy_mode: document.getElementById("privacy_mode").checked,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        });
        viewSettings();
      } catch (err) {
        document.getElementById("form-error").innerHTML = bannerFor(err);
      }
    });
    document.querySelectorAll("[data-consent-toggle]").forEach((el) =>
      el.addEventListener("change", async () => {
        const consentType = el.getAttribute("data-consent-toggle");
        el.disabled = true;
        try {
          if (el.checked) {
            await OvaCareAPI.submitConsent({ consent_type: consentType, accepted: true, ...CONSENT_META });
          } else {
            await OvaCareAPI.withdrawConsent(consentType);
          }
        } catch (err) {
          mount(bannerFor(err));
          return;
        }
        viewSettings();
      })
    );
  } catch (err) {
    mount(bannerFor(err));
  }
}

// ---------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------

const ROUTES = {
  "#/login": { view: viewLogin, public: true },
  "#/register": { view: viewRegister, public: true },
  "#/consent": { view: viewConsent, public: false },
  "#/dashboard": { view: viewDashboard, public: false },
  "#/cycles": { view: viewCycles, public: false },
  "#/symptoms": { view: viewSymptoms, public: false },
  "#/assessment": { view: viewAssessment, public: false },
  "#/history": { view: viewHistory, public: false },
  "#/insights": { view: viewInsights, public: false },
  "#/profile": { view: viewProfile, public: false },
  "#/settings": { view: viewSettings, public: false },
};

function router() {
  let hash = location.hash || (OvaCareAPI.isAuthenticated() ? "#/dashboard" : "#/login");
  if (!ROUTES[hash]) hash = OvaCareAPI.isAuthenticated() ? "#/dashboard" : "#/login";

  const route = ROUTES[hash];
  if (!route.public && !OvaCareAPI.isAuthenticated()) {
    location.hash = "#/login";
    return;
  }
  if (route.public && OvaCareAPI.isAuthenticated() && (hash === "#/login" || hash === "#/register")) {
    location.hash = "#/dashboard";
    return;
  }

  renderShell();
  setActiveNav(hash);
  route.view();
}

window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", router);
