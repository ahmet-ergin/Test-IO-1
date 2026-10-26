import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const http = axios.create({ baseURL: API });

export const errMsg = (e, fallback = "Error") =>
  e?.response?.data?.error?.message || e?.response?.data?.detail?.[0]?.msg || e?.message || fallback;

export const artifactUrl = (id) => (id ? `${API}/artifacts/${id}` : null);

export async function downloadExport(sessionId) {
  const { data } = await http.get(`/sessions/${sessionId}/export`);
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `recording-${sessionId}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export const fmtDuration = (ms) => {
  const s = Math.floor((ms || 0) / 1000);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`;
};

export const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString() : "—");
