const API_BASE = import.meta.env.VITE_API_BASE
  || (["5173", "4173"].includes(window.location.port) ? "/api/v1" : `${window.location.origin}/api/v1`);

export function getSessionId() {
  let sessionId = localStorage.getItem("zmark.session_id");
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem("zmark.session_id", sessionId);
  }
  return sessionId;
}

export function resetSessionId() {
  const sessionId = crypto.randomUUID();
  localStorage.setItem("zmark.session_id", sessionId);
  return sessionId;
}

async function request(path, options = {}) {
  const headers = {
    "X-Session-ID": getSessionId(),
    ...(options.headers || {}),
  };
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.message || body.detail || `Request failed: ${response.status}`);
  }
  return body;
}

export async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/upload", { method: "POST", body: form });
}

export async function getSchema(fileId) {
  return request(`/upload/${fileId}/schema`);
}

export async function getDashboard() {
  return request("/dashboard");
}

export async function getSessionFiles() {
  return request("/session/files");
}

export async function clearSession() {
  return request("/session", { method: "DELETE" });
}

export async function runMonteCarlo({ product, budgetChangePct, horizonDays, simulations = 5000 }) {
  return request("/power/monte-carlo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product,
      budget_change_pct: budgetChangePct,
      horizon_days: horizonDays,
      simulations,
    }),
  });
}

export async function sendChat(query, history) {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, history }),
  });
}

export async function streamChat(query, history, onEvent) {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": getSessionId(),
    },
    body: JSON.stringify({ query, history }),
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.message || body.detail || `Request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      onEvent(JSON.parse(line));
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}

export async function ping() {
  try {
    const response = await fetch(API_BASE.replace("/api/v1", "/"));
    return response.ok;
  } catch {
    return false;
  }
}
