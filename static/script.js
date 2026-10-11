

const API = {
  async _handle(res) {
    let data;
    try {
      data = await res.json();
    } catch (e) {
      throw new Error("The server returned an unexpected response.");
    }
    if (!res.ok || data.success === false) {
      throw new Error(data.error || "Something went wrong.");
    }
    return data;
  },
  
  async _fetchWithTimeout(url, opts, timeoutMs = 60000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...opts, signal: controller.signal });
    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error("The request took too long and was cancelled. Please try again.");
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  },
  get(url) {
    return this._fetchWithTimeout(url, {}).then(this._handle);
  },
  post(url, body) {
    return this._fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(this._handle);
  },
  postForm(url, formData) {

    return this._fetchWithTimeout(url, { method: "POST", body: formData }, 90000).then(this._handle);
  },
  del(url) {
    return this._fetchWithTimeout(url, { method: "DELETE" }).then(this._handle);
  },
};

function showToast(message, type = "info", options = {}) {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  const text = document.createElement("span");
  text.className = "toast-text";
  text.textContent = message;
  toast.appendChild(text);

  if (options.onRetry) {
    const retryBtn = document.createElement("button");
    retryBtn.type = "button";
    retryBtn.className = "toast-retry-btn";
    retryBtn.textContent = options.retryLabel || "Try Again";
    retryBtn.addEventListener("click", () => {
      toast.remove();
      options.onRetry();
    });
    toast.appendChild(retryBtn);
  }

  container.appendChild(toast);

  setTimeout(() => toast.remove(), options.onRetry ? 9000 : 5000);
}

function friendlyAiErrorMessage(raw) {
  if (!raw) return "Something went wrong. Please try again.";

  const looksLikeNetworkFailure = /failed to fetch|networkerror|network error|load failed|err_connection|err_network|err_internet/i.test(raw);
  if (looksLikeNetworkFailure) {
    console.error("Network error (raw, for debugging):", raw);
    return "Could not reach the server. Please check your connection and try again.";
  }

  const looksLikeAiError = /gemini|anthropic|claude|\bai api\b|ai_api_key|overloaded|status 5\d\d|status 429|\bunavailable\b|rate.?limit|took too long/i.test(raw);
  if (looksLikeAiError) {
    console.error("AI provider error (raw, for debugging):", raw);
    return "AI service is temporarily unavailable. Please try again in a moment.";
  }

  return raw;
}

function setBtnLoading(btn, loading) {
  if (!btn) return;
  const label = btn.querySelector(".btn-label");
  const spinner = btn.querySelector(".btn-spinner");
  btn.disabled = loading;
  if (spinner) {
    spinner.hidden = !loading;
    spinner.style.display = loading ? "inline-block" : "none";
  }
  if (label) label.style.opacity = loading ? 0.6 : 1;
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function priorityBadgeClass(level) {
  return `badge-${(level || "medium").toLowerCase()}`;
}

function priorityColorVar(level) {
  const map = { CRITICAL: "var(--critical)", HIGH: "var(--high)", MEDIUM: "var(--blue)", LOW: "var(--low)" };
  return map[level] || "var(--blue)";
}

const ICONS = {
  inbox: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 12h4.2l1.6 3h5.4l1.6-3h4.2"/><path d="M5.2 6.2 3.5 12v6a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-6l-1.7-5.8A2 2 0 0 0 17 4.5H7a2 2 0 0 0-1.8 1.7z"/></svg>`,
  calendar: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4.5" width="18" height="16" rx="2"/><line x1="3" y1="9.5" x2="21" y2="9.5"/><line x1="8" y1="2.5" x2="8" y2="6.5"/><line x1="16" y1="2.5" x2="16" y2="6.5"/></svg>`,
  fileText: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2.5H7a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><polyline points="14 2.5 14 8 19.5 8"/><line x1="8.5" y1="13" x2="15.5" y2="13"/><line x1="8.5" y1="17" x2="15.5" y2="17"/></svg>`,
  helpCircle: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.2a2.5 2.5 0 0 1 4.9.8c0 1.7-2.4 2-2.4 3.5"/><line x1="12" y1="17" x2="12" y2="17"/></svg>`,
  trendingUp: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 6"/><polyline points="14 6 21 6 21 13"/></svg>`,
  barChart: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="21" x2="5" y2="12"/><line x1="12" y1="21" x2="12" y2="7"/><line x1="19" y1="21" x2="19" y2="15"/><line x1="3" y1="21" x2="21" y2="21"/></svg>`,
  clock: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg>`,
  checkCircle: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="8 12.5 11 15.5 16 9"/></svg>`,
  flag: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4"/><path d="M5 4.5c2-1.3 4-1.3 6 0s4 1.3 6 0v9c-2 1.3-4 1.3-6 0s-4-1.3-6 0"/></svg>`,
  percent: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="19" x2="19" y2="5"/><circle cx="7" cy="7" r="2"/><circle cx="17" cy="17" r="2"/></svg>`,
  hash: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="9" x2="19" y2="9"/><line x1="5" y1="15" x2="19" y2="15"/><line x1="9" y1="4" x2="7" y2="20"/><line x1="16" y1="4" x2="14" y2="20"/></svg>`,
  target: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></svg>`,
  layers: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2.5 21 8 12 13.5 3 8"/><polyline points="3 14 12 19.5 21 14"/></svg>`,
};

function emptyStateHtml(iconKey, message, actionHtml) {
  const icon = ICONS[iconKey] || ICONS.inbox;
  const action = actionHtml ? `<div class="empty-state-action">${actionHtml}</div>` : "";
  return `<div class="empty-state"><div class="empty-state-icon">${icon}</div><p class="empty-state-text">${escapeHtml(message)}</p>${action}</div>`;
}

function initEmptyStateActions() {
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-empty-action]");
    if (!el) return;
    const action = el.dataset.emptyAction;
    if (action === "goto-planner-form") {
      navigateTo("planner");
      setTimeout(() => document.getElementById("f-name")?.focus(), 150);
    } else if (action === "goto-generate-schedule") {
      navigateTo("planner");
      setTimeout(() => {
        document.getElementById("generate-schedule-btn")?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 150);
    } else if (action === "focus-upload") {
      document.getElementById("upload-form")?.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => document.getElementById("u-file")?.focus(), 300);
    }
  });
}

function statBox(iconKey, label, value, colorClass) {
  const icon = ICONS[iconKey] || ICONS.hash;
  const cls = colorClass ? ` ${colorClass}` : "";
  return `
    <div class="stat-box">
      <div class="stat-box-icon${cls}">${icon}</div>
      <div class="stat-box-body">
        <div class="stat-label">${escapeHtml(label)}</div>
        <div class="stat-value">${value}</div>
      </div>
    </div>`;
}

const PAGE_LOADERS = {
  planner: loadPlannerPage,
  schedule: loadSchedulePage,
  notes: loadNotesPage,
  tests: loadTestsPage,
  progress: loadProgressPage,
  analytics: loadAnalyticsPage,
};

function initNav() {
  const links = document.querySelectorAll(".nav-link, .bottom-nav-link");
  links.forEach((link) => {
    link.addEventListener("click", () => navigateTo(link.dataset.page));
  });

  const toggle = document.getElementById("nav-toggle");
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");

  function openSidebar() {
    if (sidebar) sidebar.classList.add("open");
    if (backdrop) backdrop.classList.add("active");
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("active");
  }

  if (toggle) {
    toggle.addEventListener("click", () => {
      if (sidebar && sidebar.classList.contains("open")) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }

  if (backdrop) {
    backdrop.addEventListener("click", closeSidebar);
  }

  document.addEventListener("click", (e) => {
    if (sidebar && sidebar.classList.contains("open") &&
        !sidebar.contains(e.target) && e.target !== toggle && !toggle.contains(e.target)) {
      closeSidebar();
    }
  });
}

function navigateTo(pageId) {
  document.querySelectorAll(".nav-link").forEach((l) => l.classList.toggle("active", l.dataset.page === pageId));
  document.querySelectorAll(".bottom-nav-link").forEach((l) => l.classList.toggle("active", l.dataset.page === pageId));
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === `page-${pageId}`));
  
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");
  if (sidebar) sidebar.classList.remove("open");
  if (backdrop) backdrop.classList.remove("active");

  const loader = PAGE_LOADERS[pageId];
  if (loader) loader();
}

function initPlannerForm() {
  const form = document.getElementById("subject-form");

  async function submitSubjectForm() {
    const btn = document.getElementById("analyze-btn");
    const payload = {
      name: document.getElementById("f-name").value.trim(),
      topic: document.getElementById("f-topic").value.trim(),
      deadline: document.getElementById("f-deadline").value,
      knowledge_level: document.getElementById("f-knowledge").value,
      difficulty: document.getElementById("f-difficulty").value,
      estimated_hours: document.getElementById("f-hours").value || null,
      notes: document.getElementById("f-notes").value.trim(),
    };

    setBtnLoading(btn, true);
    try {
      const res = await API.post("/api/analyze-subject", payload);
      showToast(res.warning || "Subject analyzed and added.", res.warning ? "warning" : "info");
      form.reset();
      document.getElementById("f-difficulty").value = "Auto Detect";
      await loadSubjects();
    } catch (err) {
      showToast(friendlyAiErrorMessage(err.message), "error", { onRetry: submitSubjectForm });
    } finally {
      setBtnLoading(btn, false);
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitSubjectForm();
  });

  const todayStr = new Date().toISOString().split("T")[0];
  document.getElementById("f-deadline").min = todayStr;
  document.getElementById("p-start").value = todayStr;
}

function initPreferencesForm() {
  const inputs = ["p-hours", "p-session", "p-start", "p-time"];
  inputs.forEach((id) => {
    document.getElementById(id).addEventListener("change", savePreferences);
  });
}

async function savePreferences() {
  const payload = {
    hours_per_day: parseFloat(document.getElementById("p-hours").value),
    session_length: document.getElementById("p-session").value,
    start_date: document.getElementById("p-start").value,
    preferred_time: document.getElementById("p-time").value,
  };
  try {
    await API.post("/api/preferences", payload);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function loadPreferencesIntoForm() {
  try {
    const res = await API.get("/api/preferences");
    const p = res.preferences;
    if (!p) return;
    document.getElementById("p-hours").value = p.hours_per_day;
    document.getElementById("p-session").value = p.session_length;
    document.getElementById("p-start").value = p.start_date || new Date().toISOString().split("T")[0];
    document.getElementById("p-time").value = p.preferred_time;
  } catch (err) {
    
  }
}

async function loadSubjects() {
  const list = document.getElementById("subjects-list");
  try {
    const res = await API.get("/api/subjects");
    const subjects = res.subjects || [];
    document.getElementById("subject-count").textContent = `${subjects.length} subject${subjects.length === 1 ? "" : "s"}`;

    if (subjects.length === 0) {
      list.innerHTML = emptyStateHtml(
        "inbox",
        "No subjects added yet. Add your first subject to start building your AI-powered study plan.",
        '<button type="button" class="btn btn-secondary btn-sm" data-empty-action="goto-planner-form">Add Subject</button>'
      );
      return;
    }

    list.innerHTML = subjects.map(renderSubjectCard).join("");

    list.querySelectorAll("[data-delete-subject]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.deleteSubject;
        if (!confirm("Remove this subject? This will also clear it from your schedule.")) return;
        try {
          await API.del(`/api/subjects/${id}`);
          showToast("Subject removed.");
          await loadSubjects();
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  } catch (err) {
    list.innerHTML = emptyStateHtml("inbox", `Could not load subjects: ${friendlyAiErrorMessage(err.message)}`);
  }
}

function renderSubjectCard(s) {
  const techniques = (s.study_techniques || []).map((t) => `<span class="chip">${escapeHtml(t)}</span>`).join("");
  return `
  <div class="subject-card" data-priority="${escapeHtml(s.priority_level)}">
    <div class="subject-card-top">
      <div>
        <p class="subject-card-title">${escapeHtml(s.name)}</p>
        <p class="subject-card-topic">${escapeHtml(s.topic)}</p>
      </div>
      <div style="text-align:right;">
        <span class="badge ${priorityBadgeClass(s.priority_level)}">${escapeHtml(s.priority_level)}</span>
        <div class="subject-score" style="color:${priorityColorVar(s.priority_level)}">${s.priority_score}</div>
      </div>
    </div>
    <div class="subject-meta">
      <span>Difficulty: <strong>${escapeHtml(s.difficulty)}</strong></span>
      <span>Hours: <strong>${s.estimated_hours}h</strong></span>
      <span>Deadline: <strong>${escapeHtml(s.deadline)}</strong></span>
    </div>
    ${s.study_tip ? `<div class="subject-tip">💡 ${escapeHtml(s.study_tip)}</div>` : ""}
    ${techniques ? `<div class="subject-techniques">${techniques}</div>` : ""}
    <div class="subject-actions">
      <button class="btn btn-danger btn-sm" data-delete-subject="${s.id}">Remove</button>
    </div>
  </div>`;
}

function initScheduleGenButton() {
  document.getElementById("generate-schedule-btn").addEventListener("click", async () => {
    const btn = document.getElementById("generate-schedule-btn");
    setBtnLoading(btn, true);
    try {
      await savePreferences();
      const res = await API.post("/api/generate-schedule", {});
      if (res.has_conflicts) {
        showToast(`Schedule generated, but ${res.conflicts.length} subject(s) don't fully fit before their deadline.`, "warning");
      } else {
        showToast(`Schedule generated with ${res.session_count} sessions.`);
      }
      navigateTo("schedule");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setBtnLoading(btn, false);
    }
  });
}

async function loadPlannerPage() {
  await Promise.all([loadSubjects(), loadPreferencesIntoForm()]);
}

async function loadSchedulePage({ preserveScroll = false } = {}) {
  const container = document.getElementById("schedule-content");
  const savedScroll = preserveScroll ? window.scrollY : 0;

  if (!preserveScroll) {
    container.innerHTML = `<p class="empty-state">Loading schedule...</p>`;
  }

  try {
    const res = await API.get("/api/schedule");
    const days = res.days || [];
    const conflicts = res.conflicts || [];
    const conflictsHtml = conflicts.length ? conflicts.map(renderConflictBanner).join("") : "";

    if (days.length === 0) {
      container.innerHTML = conflictsHtml + `<div class="card">${emptyStateHtml(
        "calendar",
        "No study schedule generated yet.",
        '<button type="button" class="btn btn-secondary btn-sm" data-empty-action="goto-generate-schedule">Generate AI Study Schedule</button>'
      )}</div>`;
      bindConflictButtons(container);
      return;
    }
    container.innerHTML = conflictsHtml + days.map(renderDayBlock).join("");
    bindConflictButtons(container);

    if (preserveScroll) {
      window.scrollTo({ top: savedScroll, behavior: "instant" });
    }

    container.querySelectorAll("[data-session-id]").forEach((row) => {
      row.addEventListener("click", async () => {
        const id = row.dataset.sessionId;
        try {
          await API.post(`/api/sessions/${id}/complete`, {});
          await loadSchedulePage({ preserveScroll: true });
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="card">${emptyStateHtml("calendar", `Could not load schedule: ${friendlyAiErrorMessage(err.message)}`)}</div>`;
  }
}

function renderConflictBanner(c) {
  const deadlineLabel = new Date(c.deadline + "T00:00:00").toLocaleDateString(undefined, { month: "long", day: "numeric" });
  const suggestion = c.suggested_hours_per_day
    ? `Increase daily study time from ${c.current_hours_per_day}h to ${c.suggested_hours_per_day}h, or reduce the estimated hours for this subject.`
    : `There isn't enough time left before the deadline for this subject — consider moving the deadline or reducing scope.`;
  return `
  <div class="card conflict-banner">
    <div class="conflict-title">⚠ Schedule Conflict</div>
    <p class="conflict-desc">
      <strong>${escapeHtml(c.subject_name)}</strong> (${escapeHtml(c.topic)}) requires
      <strong>${c.required_hours}h</strong> before ${escapeHtml(deadlineLabel)}, but only
      <strong>${c.available_hours}h</strong> are currently available.
    </p>
    <div class="conflict-stats">
      <div><span class="muted">Required</span><strong>${c.required_hours}h</strong></div>
      <div><span class="muted">Available</span><strong>${c.available_hours}h</strong></div>
      <div><span class="muted">Shortage</span><strong style="color:var(--critical)">${c.missing_hours}h</strong></div>
    </div>
    <p class="conflict-suggestion">💡 Suggestion: ${escapeHtml(suggestion)}</p>
    ${c.suggested_hours_per_day ? `
      <button class="btn btn-secondary btn-sm" data-apply-suggestion="${c.suggested_hours_per_day}">
        Use ${c.suggested_hours_per_day}h/day &amp; regenerate
      </button>` : ""}
  </div>`;
}

function bindConflictButtons(container) {
  container.querySelectorAll("[data-apply-suggestion]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const suggested = btn.dataset.applySuggestion;
      const ok = confirm(
        `This will change your Study Hours Per Day to ${suggested}h and regenerate your schedule. Continue?`
      );
      if (!ok) return;
      try {
        document.getElementById("p-hours").value = suggested;
        await savePreferences();
        const res = await API.post("/api/generate-schedule", {});
        showToast(res.has_conflicts ? "Schedule regenerated — some conflicts remain." : "Schedule regenerated, conflict resolved.");
        await loadSchedulePage();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });
}

function renderDayBlock(day) {
  const dateLabel = new Date(day.date + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric",
  });
  const sessions = day.sessions.map(renderSessionRow).join("");
  return `
  <div class="card day-block">
    <div class="day-header">
      <h3>${escapeHtml(dateLabel)}</h3>
      <div class="day-stats">
        <span>${day.total_hours}h total</span>
        <span>${day.completed_count}/${day.session_count} done</span>
      </div>
    </div>
    ${sessions}
  </div>`;
}

function renderSessionRow(s) {
  if (s.is_break) {
    return `
    <div class="session-row is-break">
      <span class="session-time">${escapeHtml(s.start_time)} – ${escapeHtml(s.end_time)}</span>
      <div class="session-info"><span class="session-subject">Break</span></div>
    </div>`;
  }
  const completedClass = s.completed ? "completed" : "";
  return `
  <div class="session-row ${completedClass}" data-session-id="${s.id}">
    <span class="session-time">${escapeHtml(s.start_time)} – ${escapeHtml(s.end_time)}</span>
    <div class="session-info">
      <div class="session-subject">${escapeHtml(s.subject_name)} <span class="badge ${priorityBadgeClass(s.priority_level)}" style="margin-left:6px;">${escapeHtml(s.priority_level)}</span></div>
      <div class="session-topic">${escapeHtml(s.topic)}</div>
      ${s.technique ? `<div class="session-technique">${escapeHtml(s.technique)}</div>` : ""}
    </div>
    <div class="check-circle">${s.completed ? "✓" : ""}</div>
  </div>`;
}

function initUploadForm() {
  const form = document.getElementById("upload-form");

  async function submitUploadForm() {
    const btn = document.getElementById("upload-btn");
    const fileInput = document.getElementById("u-file");
    if (!fileInput.files.length) {
      showToast("Please choose a file to upload.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("subject_name", document.getElementById("u-subject").value.trim());
    formData.append("topic", document.getElementById("u-topic").value.trim());

    setBtnLoading(btn, true);
    try {
      const res = await API.postForm("/api/upload-notes", formData);
      showToast(res.warning || "Document analyzed successfully.", res.warning ? "warning" : "info");
      form.reset();
      await loadDocuments();
    } catch (err) {
      showToast(friendlyAiErrorMessage(err.message), "error", { onRetry: submitUploadForm });
    } finally {
      setBtnLoading(btn, false);
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitUploadForm();
  });
}

async function loadDocuments() {
  const list = document.getElementById("documents-list");
  try {
    const res = await API.get("/api/documents");
    const docs = res.documents || [];
    if (docs.length === 0) {
      list.innerHTML = emptyStateHtml("fileText", "Upload your notes to analyze important topics.");
      return;
    }
    list.innerHTML = docs.map(renderDocumentCard).join("");

    list.querySelectorAll("[data-generate-mcq]").forEach((btn) => {
      btn.addEventListener("click", () => showMcqPanel(btn));
    });
  } catch (err) {
    list.innerHTML = emptyStateHtml("fileText", `Could not load documents: ${friendlyAiErrorMessage(err.message)}`);
  }
}

function renderDocumentCard(doc) {
  const topics = (doc.important_topics || []).slice(0, 8).map((t) => `<span class="topic-tag">${escapeHtml(t)}</span>`).join("");
  const definitions = (doc.key_definitions || []).slice(0, 5).map((d) => `<li>${escapeHtml(d)}</li>`).join("");
  const facts = (doc.important_facts || []).slice(0, 5).map((f) => `<li>${escapeHtml(f)}</li>`).join("");
  const revision = (doc.revision_areas || []).slice(0, 5).map((r) => `<li>${escapeHtml(r)}</li>`).join("");

  return `
  <div class="document-card">
    <div class="document-card-top">
      <div>
        <p class="document-title">${escapeHtml(doc.subject_name || "Untitled")} — ${escapeHtml(doc.topic || "")}</p>
        <span class="doc-file-tag">${escapeHtml(doc.filename)}</span>
      </div>
      <button class="btn btn-primary btn-sm" data-generate-mcq="${doc.id}"
        data-subject="${escapeHtml(doc.subject_name || "")}" data-topic="${escapeHtml(doc.topic || "")}">
        Generate Mock Test
      </button>
    </div>
    ${doc.analysis_error ? `<p class="doc-warning">⚠ ${escapeHtml(doc.analysis_error)}</p>` : ""}
    ${topics ? `<div class="doc-section-label">Important Topics</div><div class="topic-tags">${topics}</div>` : ""}
    ${definitions ? `<div class="doc-section-label">Key Definitions</div><ul class="doc-list">${definitions}</ul>` : ""}
    ${facts ? `<div class="doc-section-label">Important Facts</div><ul class="doc-list">${facts}</ul>` : ""}
    ${revision ? `<div class="doc-section-label">Focus For Revision</div><ul class="doc-list">${revision}</ul>` : ""}
    <div id="mcq-panel-${doc.id}"></div>
  </div>`;
}

function showMcqPanel(btn) {
  const docId = btn.dataset.generateMcq;
  const subject = btn.dataset.subject;
  const topic = btn.dataset.topic;
  const container = document.getElementById(`mcq-panel-${docId}`);

  if (container.querySelector(".mcq-generate-panel")) {
    container.innerHTML = "";
    return;
  }

  const tpl = document.getElementById("tpl-mcq-panel").content.cloneNode(true);
  tpl.querySelector("h3").textContent = "How many questions?";
  tpl.querySelector("p").textContent = `Generate a mock test for ${subject} — ${topic}, based only on this document.`;
  const wrapper = document.createElement("div");
  wrapper.appendChild(tpl);
  container.innerHTML = "";
  container.appendChild(wrapper);

  container.querySelectorAll("[data-count]").forEach((countBtn) => {
    const n = parseInt(countBtn.dataset.count, 10);

    async function attemptGenerateMcq() {
      countBtn.disabled = true;
      countBtn.textContent = "Generating...";
      try {
        const res = await API.post("/api/generate-mcq", { document_id: parseInt(docId, 10), num_questions: n });
        if (res.insufficient_material) {
          showToast(res.warning || `Only ${res.num_questions} of ${n} questions could be generated from this document.`, "warning");
        } else {
          showToast(`Mock test generated with ${res.num_questions} questions, all sourced from your document.`);
        }
        container.innerHTML = "";
        navigateTo("tests");
      } catch (err) {
        showToast(friendlyAiErrorMessage(err.message), "error", { onRetry: attemptGenerateMcq });
        countBtn.disabled = false;
        countBtn.textContent = `${n} Questions`;
      }
    }

    countBtn.addEventListener("click", attemptGenerateMcq);
  });
}

async function loadNotesPage() {
  await loadDocuments();
}

let currentTest = null;
let currentAnswers = [];
let currentQIndex = 0;

async function loadTestsPage() {
  document.getElementById("tests-list-view").classList.remove("hidden");
  document.getElementById("test-taking-view").classList.add("hidden");
  document.getElementById("test-result-view").classList.add("hidden");

  const list = document.getElementById("mock-tests-list");
  try {
    const res = await API.get("/api/mock-tests");
    const tests = res.mock_tests || [];
    if (tests.length === 0) {
      list.innerHTML = emptyStateHtml("helpCircle", "Analyze a document in Study Notes, then generate a test here.");
      return;
    }
    list.innerHTML = tests.map((t) => `
      <div class="test-card">
        <div class="test-card-info">
          <h3>${escapeHtml(t.subject_name || "Untitled")} — ${escapeHtml(t.topic || "")}</h3>
          <p>${t.num_questions} Questions · Generated from: ${escapeHtml(t.source_filename || "document")}</p>
        </div>
        <button class="btn btn-primary" data-start-test="${t.id}">Start Test</button>
      </div>
    `).join("");

    list.querySelectorAll("[data-start-test]").forEach((btn) => {
      btn.addEventListener("click", () => startTest(btn.dataset.startTest));
    });
  } catch (err) {
    list.innerHTML = emptyStateHtml("helpCircle", `Could not load mock tests: ${friendlyAiErrorMessage(err.message)}`);
  }
}

async function startTest(testId) {
  try {
    const res = await API.get(`/api/mock-tests/${testId}`);
    currentTest = res;
    currentAnswers = new Array(res.questions.length).fill(null);
    currentQIndex = 0;

    document.getElementById("tests-list-view").classList.add("hidden");
    document.getElementById("test-result-view").classList.add("hidden");
    document.getElementById("test-taking-view").classList.remove("hidden");
    renderCurrentQuestion();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderCurrentQuestion() {
  const view = document.getElementById("test-taking-view");
  const q = currentTest.questions[currentQIndex];
  const letters = ["A", "B", "C", "D"];

  const dots = currentTest.questions.map((_, i) => {
    const cls = ["q-dot"];
    if (i === currentQIndex) cls.push("active");
    else if (currentAnswers[i] !== null) cls.push("answered");
    return `<button class="${cls.join(" ")}" data-goto="${i}">${i + 1}</button>`;
  }).join("");

  const options = q.options.map((opt, i) => {
    const selected = currentAnswers[currentQIndex] === opt ? "selected" : "";
    return `
      <div class="option-item ${selected}" data-option-index="${i}">
        <span class="option-letter">${letters[i]}</span>
        <span>${escapeHtml(opt)}</span>
      </div>`;
  }).join("");

  view.innerHTML = `
    <div class="question-panel">
      <div class="question-progress">Question ${currentQIndex + 1} of ${currentTest.questions.length} · ${escapeHtml(currentTest.subject_name)} — ${escapeHtml(currentTest.topic)}</div>
      <p class="question-text">${escapeHtml(q.question)}</p>
      <div class="option-list">${options}</div>
      <div class="test-nav-row">
        <button class="btn btn-secondary" id="prev-q-btn" ${currentQIndex === 0 ? "disabled" : ""}>Previous</button>
        <div class="question-dots">${dots}</div>
        ${currentQIndex === currentTest.questions.length - 1
          ? `<button class="btn btn-primary" id="submit-test-btn">Submit Test</button>`
          : `<button class="btn btn-secondary" id="next-q-btn">Next</button>`}
      </div>
    </div>
  `;

  view.querySelectorAll("[data-option-index]").forEach((el) => {
    el.addEventListener("click", () => {
      currentAnswers[currentQIndex] = q.options[parseInt(el.dataset.optionIndex, 10)];
      renderCurrentQuestion();
    });
  });
  view.querySelectorAll("[data-goto]").forEach((el) => {
    el.addEventListener("click", () => {
      currentQIndex = parseInt(el.dataset.goto, 10);
      renderCurrentQuestion();
    });
  });
  const prevBtn = document.getElementById("prev-q-btn");
  if (prevBtn) prevBtn.addEventListener("click", () => { currentQIndex--; renderCurrentQuestion(); });
  const nextBtn = document.getElementById("next-q-btn");
  if (nextBtn) nextBtn.addEventListener("click", () => { currentQIndex++; renderCurrentQuestion(); });
  const submitBtn = document.getElementById("submit-test-btn");
  if (submitBtn) submitBtn.addEventListener("click", submitCurrentTest);
}

async function submitCurrentTest() {
  const unanswered = currentAnswers.filter((a) => a === null).length;
  if (unanswered > 0) {
    if (!confirm(`You have ${unanswered} unanswered question(s). Submit anyway?`)) return;
  }
  try {
    const res = await API.post("/api/submit-test", { mock_test_id: currentTest.id, answers: currentAnswers });
    renderTestResult(res);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderTestResult(res) {
  document.getElementById("test-taking-view").classList.add("hidden");
  const view = document.getElementById("test-result-view");
  view.classList.remove("hidden");

  const perfColor = { Excellent: "var(--low)", Good: "var(--blue)", Fair: "var(--high)", "Needs Improvement": "var(--critical)" }[res.performance] || "var(--blue)";

  const questionResults = res.results.map((r, i) => `
    <div class="result-question">
      <div class="result-question-head">
        <strong>Q${i + 1}. ${escapeHtml(r.question)}</strong>
        <span class="badge ${r.is_correct ? "badge-low" : "badge-critical"}">${r.is_correct ? "Correct" : "Incorrect"}</span>
      </div>
      <div class="muted">Your answer: ${escapeHtml(r.user_answer || "— none —")}</div>
      <div class="muted">Correct answer: ${escapeHtml(r.correct_answer)}</div>
      ${r.explanation ? `<div class="result-explanation">${escapeHtml(r.explanation)}</div>` : ""}
      ${r.source_reference ? `<div class="result-source"><span class="doc-section-label">From your document</span>${escapeHtml(r.source_reference)}</div>` : ""}
    </div>
  `).join("");

  view.innerHTML = `
    <div class="card result-summary">
      <div class="muted">Score</div>
      <div class="result-score">${res.score} / ${res.total_questions}</div>
      <div class="muted">${res.percentage}% · ${res.correct_answers} correct · ${res.wrong_answers} wrong</div>
      <span class="badge result-performance" style="color:${perfColor}; background: color-mix(in srgb, ${perfColor} 15%, transparent);">${escapeHtml(res.performance)}</span>
    </div>
    <div class="card">
      <h2>Question-wise Result</h2>
      ${questionResults}
    </div>
    <button class="btn btn-secondary" id="back-to-tests-btn">Back to Mock Tests</button>
  `;

  document.getElementById("back-to-tests-btn").addEventListener("click", () => {
    view.classList.add("hidden");
    document.getElementById("tests-list-view").classList.remove("hidden");
    loadTestsPage();
  });
}

async function loadProgressPage() {
  const container = document.getElementById("progress-content");
  container.innerHTML = `<p class="empty-state">Loading progress...</p>`;
  try {
    const res = await API.get("/api/progress");
    const { subject_progress, overall, mock_test_results } = res;

    const ringCircumference = 2 * Math.PI * 54;
    const ringOffset = ringCircumference * (1 - (overall.completion_percentage || 0) / 100);

    const subjectsHtml = subject_progress.length === 0
      ? emptyStateHtml(
          "inbox",
          "No subjects yet. Add subjects in Planner to see your progress here.",
          '<button type="button" class="btn btn-secondary btn-sm" data-empty-action="goto-planner-form">Add Subject</button>'
        )
      : subject_progress.map((s) => `
        <div class="progress-item">
          <div class="progress-row">
            <strong>${escapeHtml(s.name)} <span class="muted">— ${escapeHtml(s.topic)}</span></strong>
            <span class="muted">${s.completed_hours} / ${s.planned_hours} hrs</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:${s.completion_percentage}%; background: ${priorityColorVar(s.priority_level)};"></div></div>
        </div>
      `).join("");

    const testsHtml = (mock_test_results || []).length === 0
      ? emptyStateHtml("helpCircle", "Take a mock test to see your scores here.")
      : mock_test_results.map((t) => `
        <div class="progress-row">
          <span>${escapeHtml(t.subject_name)} — ${escapeHtml(t.topic)}</span>
          <span class="muted">${t.correct_answers}/${t.total_questions} (${t.percentage}%) · ${escapeHtml(t.performance)}</span>
        </div>
      `).join("");

    container.innerHTML = `
      <div class="card">
        <h2>Overall Progress</h2>
        <div class="ring-wrap">
          <div class="ring">
            <svg width="128" height="128" viewBox="0 0 128 128">
              <circle cx="64" cy="64" r="54" stroke="var(--surface-3)" stroke-width="12" fill="none"/>
              <circle cx="64" cy="64" r="54" stroke="url(#ringGrad)" stroke-width="12" fill="none"
                stroke-dasharray="${ringCircumference}" stroke-dashoffset="${ringOffset}" stroke-linecap="round"/>
              <defs>
                <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#2563EB"/>
                  <stop offset="100%" stop-color="#4F46E5"/>
                </linearGradient>
              </defs>
            </svg>
            <div class="ring-value">${overall.completion_percentage}%</div>
          </div>
          <div class="ring-stats">
            ${statBox("clock", "Total Planned Hours", `${overall.total_planned_hours}h`, "icon-blue")}
            ${statBox("checkCircle", "Completed Hours", `${overall.total_completed_hours}h`, "icon-green")}
            ${statBox("hash", "Remaining Hours", `${Math.max(overall.total_planned_hours - overall.total_completed_hours, 0).toFixed(2)}h`, "icon-amber")}
            ${statBox("flag", "Sessions Completed", `${overall.completed_sessions}/${overall.total_sessions}`)}
          </div>
        </div>
      </div>
      <div class="card">
        <h2>Subject-wise Progress</h2>
        ${subjectsHtml}
      </div>
      <div class="card">
        <h2>Mock Test Scores</h2>
        ${testsHtml}
      </div>
    `;
  } catch (err) {
    container.innerHTML = emptyStateHtml("trendingUp", `Could not load progress: ${friendlyAiErrorMessage(err.message)}`);
  }
}

let progressChartInstance = null;

async function loadAnalyticsPage() {
  const container = document.getElementById("analytics-content");
  container.innerHTML = `<p class="empty-state">Loading analytics...</p>`;
  try {
    const res = await API.get("/api/analytics");
    const a = res.analytics;

    const priorityRows = ["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((level) => {
      const count = a.priority_distribution[level] || 0;
      const pct = a.total_subjects ? Math.round((count / a.total_subjects) * 100) : 0;
      return `
        <div class="priority-bar-row">
          <span class="priority-bar-label">${level}</span>
          <div class="priority-bar-track"><div class="priority-bar-fill" style="width:${pct}%; background:${priorityColorVar(level)};"></div></div>
          <span class="priority-bar-count">${count}</span>
        </div>`;
    }).join("");

    const subjectHoursRows = a.subject_hours.length === 0
      ? emptyStateHtml("barChart", "Complete a few study sessions to see your progress analytics.")
      : a.subject_hours.map((s) => {
          const pct = s.planned_hours ? Math.round((s.completed_hours / s.planned_hours) * 100) : 0;
          return `
          <div class="progress-item">
            <div class="progress-row"><span>${escapeHtml(s.name)} — ${escapeHtml(s.topic)}</span><span class="muted">${s.completed_hours}/${s.planned_hours}h</span></div>
            <div class="progress-track"><div class="progress-fill" style="width:${pct}%;"></div></div>
          </div>`;
        }).join("");

    const insightsHtml = (a.ai_insights || []).map((insight) => `
      <div class="insight-card"><span class="insight-icon">✦</span><span>${escapeHtml(insight)}</span></div>
    `).join("");

    const remainingHours = Math.max(a.total_planned_hours - a.total_completed_hours, 0);
    const chart = a.progress_chart || { labels: [], actual: [], has_data: false };
    const hasChartData = chart.has_data;

    const isSinglePoint = hasChartData && chart.actual.length === 1;

    container.innerHTML = `
      <div class="stats-grid">
        ${statBox("clock", "Planned Hours", `${a.total_planned_hours}h`, "icon-blue")}
        ${statBox("checkCircle", "Completed Hours", `${a.total_completed_hours}h`, "icon-green")}
        ${statBox("percent", "Overall Progress", `${a.overall_progress_percentage}%`)}
        ${statBox("hash", "Total Subjects", a.total_subjects)}
        ${statBox("flag", "Critical Subjects", a.critical_subjects, "icon-red")}
        ${statBox("layers", "Mock Tests Taken", a.total_mock_tests_taken)}
        ${statBox("target", "Avg Test Score", a.avg_test_score !== null ? a.avg_test_score + "%" : "—")}
        ${statBox("checkCircle", "Sessions Completed", `${a.total_sessions_completed}/${a.total_sessions}`, "icon-green")}
      </div>

      <div class="card">
        <h2>Study Progress</h2>
        <p class="muted" style="margin:-4px 0 16px;font-size:0.85rem;">Cumulative study hours over time</p>
        ${hasChartData ? `
          <div class="chart-summary-row">
            <div class="chart-summary-item"><div class="stat-label">Completed</div><div class="stat-value">${a.total_completed_hours}h</div></div>
            <div class="chart-summary-item"><div class="stat-label">Planned</div><div class="stat-value">${a.total_planned_hours}h</div></div>
            <div class="chart-summary-item"><div class="stat-label">Remaining</div><div class="stat-value">${remainingHours.toFixed(2)}h</div></div>
            <div class="chart-summary-item"><div class="stat-label">Completion</div><div class="stat-value">${a.overall_progress_percentage}%</div></div>
          </div>
          <div class="chart-container"><canvas id="progress-chart"></canvas></div>
          ${isSinglePoint ? `<p class="chart-hint">📅 Complete more study sessions to see your progress trend over time.</p>` : ""}
        ` : `
          <div class="empty-state">
            <div class="empty-state-icon">${ICONS.trendingUp}</div>
            <p class="empty-state-text">No study progress yet</p>
            <p class="muted" style="font-size:0.82rem;margin-top:4px;">Complete your study sessions to see your progress over time.</p>
          </div>
        `}
      </div>

      <div class="card">
        <h2>Priority Distribution</h2>
        ${priorityRows}
      </div>

      <div class="card">
        <h2>Subject-wise Study Hours</h2>
        ${subjectHoursRows}
      </div>

      <div class="card">
        <h2>AI Study Insights</h2>
        ${insightsHtml || emptyStateHtml("trendingUp", "Add subjects and complete sessions to get personalized insights.")}
      </div>
    `;

    if (hasChartData) renderProgressChart(chart, isSinglePoint);
  } catch (err) {
    container.innerHTML = emptyStateHtml("barChart", `Could not load analytics: ${friendlyAiErrorMessage(err.message)}`);
  }
}

function renderProgressChart(chart, isSinglePoint) {
  const canvas = document.getElementById("progress-chart");
  if (!canvas || typeof Chart === "undefined") return;

  if (progressChartInstance) {
    progressChartInstance.destroy();
    progressChartInstance = null;
  }

  const maxVal = Math.max(...chart.actual, 0);

  const yStep = maxVal <= 3 ? 0.5 : maxVal <= 10 ? 1 : maxVal <= 20 ? 2 : 5;

  const suggestedMax = isSinglePoint
    ? Math.max(maxVal * 1.7, maxVal + 1)
    : maxVal + yStep;

  const singlePointPlugin = {
    id: "singlePointDrop",
    afterDraw(ch) {
      if (!isSinglePoint) return;
      const meta = ch.getDatasetMeta(0);
      if (!meta || !meta.data.length) return;
      const pt = meta.data[0];
      const { ctx, scales: { y } } = ch;
      const val = chart.actual[0];

      ctx.save();

      ctx.beginPath();
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = "rgba(37,99,235,0.40)";
      ctx.lineWidth = 1.5;
      ctx.moveTo(pt.x, pt.y + 9);
      ctx.lineTo(pt.x, y.bottom);
      ctx.stroke();

      ctx.setLineDash([]);
      ctx.fillStyle = "#1E40AF";
      ctx.font = "600 13px 'Inter', sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.fillText(val + "h", pt.x, pt.y - 12);

      ctx.restore();
    },
  };

  progressChartInstance = new Chart(canvas.getContext("2d"), {
    type: "line",
    plugins: [singlePointPlugin],
    data: {
      labels: chart.labels,
      datasets: [
        {
          label: "Study Progress",
          data: chart.actual,
          borderColor: "#1CB0F6",
          backgroundColor: "rgba(28, 176, 246, 0.12)",
          borderWidth: isSinglePoint ? 0 : 3,
          tension: 0.35,
          pointRadius: isSinglePoint ? 8 : (ctx) => (ctx.raw > 0 ? 6 : 3),
          pointHoverRadius: isSinglePoint ? 10 : 8,
          pointBackgroundColor: "#1CB0F6",
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          fill: !isSinglePoint,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        title:  { display: false },
        tooltip: {
          backgroundColor: "#1E293B",
          titleColor: "#94A3B8",
          bodyColor: "#F1F5F9",
          padding: 12,
          cornerRadius: 12,
          titleFont: { family: "Nunito", weight: "700" },
          bodyFont: { family: "Nunito", weight: "800" },
          callbacks: {
            title: (items) => items[0]?.label || "",
            label: (ctx)  => `  Cumulative Hours: ${ctx.formattedValue}h`,
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Date",  color: "#64748B", font: { family: "Nunito", size: 12, weight: "700" } },
          ticks: { color: "#64748B", font: { family: "Nunito", size: 11, weight: "600" }, maxRotation: 45 },
          grid:  { color: "#F1F5F9", lineWidth: 1 },
          border: { color: "#E2E8F0" },
        },
        y: {
          title: { display: true, text: "Hours", color: "#64748B", font: { family: "Nunito", size: 12, weight: "700" } },
          ticks: {
            color: "#64748B",
            font:  { family: "Nunito", size: 11, weight: "700" },
            stepSize: yStep,
            callback: (v) => v + "h",
          },
          grid:  { color: "#F1F5F9", lineWidth: 1 },
          border: { color: "#E2E8F0", dash: [4, 4] },
          beginAtZero: true,
          suggestedMax,
        },
      },
    },
  });
}

let deferredPrompt = null;

function initPWAAndMobile() {
  // 1. Register Service Worker
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker
        .register("/sw.js")
        .then((reg) => {
          console.log("[PWA] ServiceWorker registered with scope:", reg.scope);
        })
        .catch((err) => {
          console.warn("[PWA] ServiceWorker registration failed:", err);
        });
    });
  }

  // 2. Handle beforeinstallprompt (Android / Chrome / Edge)
  const installBanner = document.getElementById("pwa-install-banner");
  const installTopBtn = document.getElementById("mobile-install-top-btn");
  const bannerInstallBtn = document.getElementById("btn-pwa-install");
  const bannerDismissBtn = document.getElementById("btn-pwa-dismiss");

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;

    const dismissedAt = localStorage.getItem("studyai_pwa_dismissed");
    const dayPassed = !dismissedAt || (Date.now() - Number(dismissedAt) > 86400000);

    if (dayPassed && installBanner) {
      installBanner.classList.remove("hidden");
    }
    if (installTopBtn) {
      installTopBtn.classList.remove("hidden");
    }
  });

  async function triggerInstall() {
    if (!deferredPrompt) {
      openMobileSyncModal();
      return;
    }
    deferredPrompt.prompt();
    try {
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === "accepted") {
        showToast("Installing AI Study Scheduler...", "info");
        if (installBanner) installBanner.classList.add("hidden");
        if (installTopBtn) installTopBtn.classList.add("hidden");
      }
    } catch (e) {
      console.warn("Install prompt dismissed or failed:", e);
    }
    deferredPrompt = null;
  }

  if (bannerInstallBtn) bannerInstallBtn.addEventListener("click", triggerInstall);
  if (installTopBtn) installTopBtn.addEventListener("click", triggerInstall);

  if (bannerDismissBtn) {
    bannerDismissBtn.addEventListener("click", () => {
      if (installBanner) installBanner.classList.add("hidden");
      localStorage.setItem("studyai_pwa_dismissed", Date.now());
    });
  }

  window.addEventListener("appinstalled", () => {
    showToast("🎉 AI Study Scheduler installed! Launch it from your home screen.", "info");
    if (installBanner) installBanner.classList.add("hidden");
    if (installTopBtn) installTopBtn.classList.add("hidden");
    deferredPrompt = null;
  });

  // 3. Mobile Sync / QR Modal
  const syncBtn = document.getElementById("btn-mobile-sync");
  const modal = document.getElementById("mobile-sync-modal");
  const closeBtn = document.getElementById("btn-close-sync-modal");
  const copyBtn = document.getElementById("btn-copy-mobile-url");
  const urlInput = document.getElementById("mobile-url-input");
  const qrImg = document.getElementById("qr-code-img");

  async function openMobileSyncModal() {
    if (!modal) return;
    modal.classList.remove("hidden");

    let mobileUrl = window.location.origin;
    try {
      const res = await API.get("/api/mobile-info");
      if (res && res.mobile_url) {
        mobileUrl = res.mobile_url;
      }
    } catch (e) {
      mobileUrl = window.location.origin;
    }

    if (urlInput) urlInput.value = mobileUrl;
    if (qrImg) {
      qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(mobileUrl)}`;
    }
  }

  function closeMobileSyncModal() {
    if (modal) modal.classList.add("hidden");
  }

  if (syncBtn) syncBtn.addEventListener("click", openMobileSyncModal);
  if (closeBtn) closeBtn.addEventListener("click", closeMobileSyncModal);
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeMobileSyncModal();
    });
  }

  if (copyBtn && urlInput) {
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(urlInput.value);
        copyBtn.textContent = "Copied! ✓";
        setTimeout(() => { copyBtn.textContent = "Copy"; }, 2000);
      } catch (err) {
        urlInput.select();
        document.execCommand("copy");
        copyBtn.textContent = "Copied! ✓";
        setTimeout(() => { copyBtn.textContent = "Copy"; }, 2000);
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initNav();
  initPWAAndMobile();
  initEmptyStateActions();
  initPlannerForm();
  initPreferencesForm();
  initScheduleGenButton();
  initUploadForm();
  loadPlannerPage();
});

