import { useEffect, useRef, useState } from "react";
import { API, http } from "@/lib/api";

/** Live session updates over SSE, falling back to polling if the stream fails. */
export function useSessionStream(sessionId) {
  const [session, setSession] = useState(null);
  const [events, setEvents] = useState([]);
  const [mode, setMode] = useState("stream");
  const lastSeq = useRef(0);

  useEffect(() => {
    setSession(null);
    setEvents([]);
    lastSeq.current = 0;
    if (!sessionId) return undefined;
    let poll = null;
    let closed = false;
    const apply = (s, evs) => {
      setSession(s);
      if (evs?.length) {
        lastSeq.current = evs[evs.length - 1].sequence;
        setEvents((prev) => [...prev, ...evs.filter((e) => e.sequence > (prev.at(-1)?.sequence || 0))]);
      }
    };
    const startPolling = () => {
      setMode("polling");
      const tick = async () => {
        try {
          const [{ data: s }, { data: evs }] = await Promise.all([
            http.get(`/sessions/${sessionId}`), http.get(`/sessions/${sessionId}/events?after=${lastSeq.current}`)]);
          if (!closed) apply(s, evs);
        } catch { /* surfaced by status bar */ }
      };
      tick();
      poll = setInterval(tick, 1500);
    };
    const es = new EventSource(`${API}/sessions/${sessionId}/stream`);
    let gotMessage = false;
    const watchdog = setTimeout(() => { if (!gotMessage) { es.close(); startPolling(); } }, 4000);
    es.onmessage = (m) => {
      gotMessage = true;
      const d = JSON.parse(m.data);
      apply(d.session, d.events);
      if (["COMPLETED", "FAILED"].includes(d.session.status)) {
        http.get(`/sessions/${sessionId}`).then(({ data }) => !closed && setSession(data)).catch(() => {});
      }
    };
    es.onerror = () => {
      es.close();
      if (!poll && !closed) startPolling();
    };
    return () => { closed = true; clearTimeout(watchdog); es.close(); if (poll) clearInterval(poll); };
  }, [sessionId]);

  const refresh = async () => {
    if (!sessionId) return;
    const { data } = await http.get(`/sessions/${sessionId}`);
    setSession(data);
  };

  return { session, events, mode, refresh, setSession };
}
