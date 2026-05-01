import { useEffect, useState } from 'react';
import CircularGauge from '../hud/CircularGauge';
import HudArcBar from '../hud/HudArcBar';
import { api } from '../api';

type Stats = {
  cpu?: number;
  memory?: number;
  disk?: number;
  network?: number;
  uptime?: string | number;
};

function extract(v: any, keys: string[], fallback = 0): number {
  for (const k of keys) {
    const x = k.split('.').reduce((o: any, s) => (o ? o[s] : undefined), v);
    if (typeof x === 'number') return x;
    if (typeof x === 'string' && !Number.isNaN(Number(x))) return Number(x);
  }
  return fallback;
}

export default function SystemVitals() {
  const [stats, setStats] = useState<Stats>({});

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      const s = await api.systemStats();
      if (!alive) return;
      setStats({
        cpu:     extract(s, ['cpu', 'cpu_percent', 'system.cpu']),
        memory:  extract(s, ['memory', 'memory_percent', 'system.memory']),
        disk:    extract(s, ['disk', 'disk_percent', 'system.disk']),
        network: extract(s, ['network', 'net', 'system.network'], 30),
        uptime:  s?.uptime ?? s?.system?.uptime ?? '—',
      });
    };
    refresh();
    const t = setInterval(refresh, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div className="system-vitals">
      <div className="gauges-row">
        <CircularGauge label="CPU"  value={stats.cpu ?? 0}    accent="cyan"    />
        <CircularGauge label="MEM"  value={stats.memory ?? 0} accent="emerald" />
        <CircularGauge label="DISK" value={stats.disk ?? 0}   accent="gold"    />
      </div>
      <HudArcBar level={stats.network ?? 0} label="NET THROUGHPUT" tone="cyan" />
      <div className="vitals-uptime">
        <span className="vu-label">UPTIME</span>
        <span className="vu-val">{String(stats.uptime)}</span>
      </div>
    </div>
  );
}
