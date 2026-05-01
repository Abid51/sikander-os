import { useEffect, useState } from 'react';
import {
  IdCard,
  MiniMap,
  TimelineStrip,
  Waveform,
  StatusStrip,
  DataTable,
  OperatorCard,
} from '../hud/OperatorWidgets';
import { api } from '../api';

export default function OperatorIntel() {
  const [sys, setSys] = useState<any>({});
  const [mon, setMon] = useState<any>({});
  const [cursor, setCursor] = useState(0);

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      const [s, m] = await Promise.all([api.systemStats(), api.monitorStats()]);
      if (!alive) return;
      setSys(s || {});
      setMon(m || {});
    };
    refresh();
    const t = setInterval(refresh, 6000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  useEffect(() => {
    const t = setInterval(() => setCursor((c) => (c + 1) % 100), 600);
    return () => clearInterval(t);
  }, []);

  const recentCalls =
    mon?.recent_calls ||
    mon?.api_calls ||
    mon?.events ||
    Array.from({ length: 5 }, (_, i) => ({
      ts: Date.now() - i * 60_000,
      ep: ['/chat', '/models/catalog', '/daemons/status', '/memory/stats', '/economy/signal'][i],
      ms: 40 + Math.floor(Math.random() * 180),
    }));

  return (
    <div className="operator-intel">
      <div className="oi-row top">
        <IdCard name="SIKANDER" code="SK-0001" rank="ARCHITECT" initials="SK" />
        <div className="oi-col">
          <StatusStrip
            items={[
              { label: 'CPU',   value: `${Math.round(sys?.cpu ?? 0)}%`, tone: 'info' },
              { label: 'MEM',   value: `${Math.round(sys?.memory ?? 0)}%`, tone: 'info' },
              { label: 'DISK',  value: `${Math.round(sys?.disk ?? 0)}%`, tone: 'ok' },
              { label: 'LAT',   value: `${Math.round(sys?.latency ?? 18)}ms`, tone: 'ok' },
            ]}
          />
          <div className="oi-waves">
            <Waveform bars={28} />
          </div>
        </div>
      </div>

      <div className="oi-row mid">
        <div className="oi-map-wrap">
          <div className="oi-head">GLOBAL NODE MAP</div>
          <MiniMap />
        </div>
        <div className="oi-ops-wrap">
          <div className="oi-head">BOUND OPERATORS</div>
          <OperatorCard name="Blood Ward"    role="Perimeter" status="ACTIVE" initials="BW" />
          <OperatorCard name="Phantom Recon" role="Network"   status="ACTIVE" initials="PR" />
          <OperatorCard name="Aether Eye"    role="Vision"    status="IDLE"   initials="AE" />
          <OperatorCard name="Chronos"       role="Temporal"  status="ACTIVE" initials="CH" />
        </div>
      </div>

      <div className="oi-row bottom">
        <div className="oi-calls">
          <div className="oi-head">RECENT API TRAFFIC</div>
          <DataTable
            rows={(Array.isArray(recentCalls) ? recentCalls : []).slice(0, 6)}
            cols={[
              { key: 'ts',  label: 'TIME',    w: '0.8', get: (r: any) => r.ts ? new Date(r.ts).toLocaleTimeString('en-GB', { hour12: false }) : '—' },
              { key: 'ep',  label: 'ENDPOINT',w: '2',   get: (r: any) => r.ep || r.endpoint || r.path || '—' },
              { key: 'ms',  label: 'MS',      w: '0.6', get: (r: any) => `${r.ms ?? r.latency_ms ?? 0}` },
            ]}
          />
        </div>
        <div className="oi-timeline">
          <div className="oi-head">MISSION TIMELINE</div>
          <TimelineStrip cursor={cursor} />
        </div>
      </div>
    </div>
  );
}
