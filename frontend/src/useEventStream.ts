import { useEffect, useRef, useState } from 'react';
import { api, authToken } from './api';

export type LiveEvent = {
  id: string;
  time: string;
  level: 'info' | 'warn' | 'alert';
  source: string;
  text: string;
};

function nowStr(): string {
  return new Date().toLocaleTimeString('en-GB', { hour12: false });
}

function mapEvent(raw: any): LiveEvent {
  const src =
    (raw?.source || raw?.daemon || raw?.subsystem || raw?.component || 'CORE')
      .toString()
      .slice(0, 14)
      .toUpperCase();
  const text =
    raw?.message || raw?.text || raw?.event || raw?.detail || JSON.stringify(raw).slice(0, 80);
  const severity = String(raw?.severity || raw?.level || '').toLowerCase();
  let level: LiveEvent['level'] = 'info';
  if (severity.startsWith('warn')) level = 'warn';
  if (severity.startsWith('err') || severity === 'critical' || severity === 'alert') level = 'alert';

  return {
    id: raw?.id || Math.random().toString(36).slice(2),
    time: raw?.timestamp
      ? new Date(raw.timestamp).toLocaleTimeString('en-GB', { hour12: false })
      : nowStr(),
    level,
    source: src,
    text: String(text).slice(0, 120),
  };
}

/**
 * Subscribes to /ws/events. Falls back gracefully if the socket fails —
 * returns connected=false so callers can display a 'simulated' badge.
 */
export function useEventStream(limit = 20) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      try {
        const tok = authToken.get();
        const base = api.wsUrl('/ws/events');
        const url = tok ? `${base}?token=${encodeURIComponent(tok)}` : base;
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (cancelled) return;
          setConnected(true);
          try { ws.send(JSON.stringify({ type: 'get_history', limit })); } catch {}
        };

        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg?.type === 'event_history' && Array.isArray(msg.events)) {
              const mapped = msg.events.map(mapEvent);
              setEvents(mapped.reverse().slice(0, limit));
            } else if (msg?.type === 'event' || msg?.event_type) {
              setEvents((cur) => [mapEvent(msg), ...cur].slice(0, limit));
            }
          } catch {
            /* ignore */
          }
        };

        ws.onclose = () => {
          if (cancelled) return;
          setConnected(false);
          setTimeout(connect, 5000);
        };

        ws.onerror = () => {
          setConnected(false);
          try { ws.close(); } catch {}
        };
      } catch {
        setConnected(false);
        setTimeout(connect, 5000);
      }
    };

    connect();

    return () => {
      cancelled = true;
      try { wsRef.current?.close(); } catch {}
    };
  }, [limit]);

  return { events, connected };
}
