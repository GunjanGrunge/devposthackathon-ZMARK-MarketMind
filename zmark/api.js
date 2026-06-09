/* api.js — ZmaRk frontend API client.
   All calls to the FastAPI backend live here.  Components import from
   window.API (set at end of file) so no bundler is required. */
(function () {
  const BASE = "http://127.0.0.1:8000/api/v1";

  // ── Session ID ──────────────────────────────────────────────────────────
  // Persisted in localStorage so refreshing keeps the same Elastic index.
  function getSessionId() {
    let sid = localStorage.getItem("zmark.session_id");
    if (!sid) {
      sid = "sess-" + Math.random().toString(36).slice(2, 10);
      localStorage.setItem("zmark.session_id", sid);
    }
    return sid;
  }

  function resetSession() {
    const sid = "sess-" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("zmark.session_id", sid);
    return sid;
  }

  // ── HTTP helper ─────────────────────────────────────────────────────────
  async function apiGet(path) {
    const sid = getSessionId();
    const res = await fetch(BASE + path, {
      headers: { "X-Session-ID": sid, "Accept": "application/json" },
    });
    if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
    return res.json();
  }

  async function apiPost(path, body) {
    const sid = getSessionId();
    const res = await fetch(BASE + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sid,
        "Accept": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API POST ${path} → ${res.status}`);
    return res.json();
  }

  // ── Upload ──────────────────────────────────────────────────────────────
  async function uploadFile(file) {
    const sid = getSessionId();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(BASE + "/upload", {
      method: "POST",
      headers: { "X-Session-ID": sid },
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || `Upload failed: ${res.status}`);
    }
    return res.json();
  }

  // ── Schema ──────────────────────────────────────────────────────────────
  async function getSchema(fileId) {
    return apiGet(`/upload/${fileId}/schema`);
  }

  // ── Dashboard ───────────────────────────────────────────────────────────
  async function getDashboard() {
    return apiGet("/dashboard");
  }

  // ── Session files ───────────────────────────────────────────────────────
  async function getSessionFiles() {
    return apiGet("/session/files");
  }

  // ── Chat ────────────────────────────────────────────────────────────────
  async function chat(query, history) {
    return apiPost("/chat", { query, history: history || [] });
  }

  // ── Power Mode: Obsolescence ────────────────────────────────────────────
  async function getObsolescence() {
    return apiGet("/power/obsolescence");
  }

  // ── Power Mode: Budget Recommender ─────────────────────────────────────
  async function getBudgetRecs() {
    return apiGet("/power/budget-recommendations");
  }

  // ── Health check ────────────────────────────────────────────────────────
  async function ping() {
    try {
      const res = await fetch("http://127.0.0.1:8000/");
      return res.ok;
    } catch {
      return false;
    }
  }

  window.API = { getSessionId, resetSession, uploadFile, getSchema, getDashboard, getSessionFiles, chat, getObsolescence, getBudgetRecs, ping };
})();
