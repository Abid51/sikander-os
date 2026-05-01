import { useEffect, useState } from 'react';
import { api } from '../api';
import DaemonCommandDrawer, { type DaemonDef } from '../DaemonCommandDrawer';

const DAEMONS: DaemonDef[] = [
  { key: 'blood_ward',    name: 'Blood Ward',    glyph: '⛨',  role: 'Perimeter Defense',   accent: 'crimson' },
  { key: 'dominion',      name: 'Dominion',      glyph: '◈',  role: 'System Dominion',     accent: 'gold'   },
  { key: 'phantom_recon', name: 'Phantom Recon', glyph: '◉',  role: 'Network Intel',       accent: 'cyan'   },
  { key: 'crimson_ledger',name: 'Crimson Ledger',glyph: '₿',  role: 'Economic Engine',     accent: 'gold'   },
  { key: 'storm_caller',  name: 'Storm Caller',  glyph: '⚡', role: 'Scheduler',           accent: 'violet' },
  { key: 'void_walker',   name: 'Void Walker',   glyph: '◎',  role: 'File Traversal',      accent: 'cyan'   },
  { key: 'aether_eye',    name: 'Aether Eye',    glyph: '👁', role: 'Vision / OCR',        accent: 'cyan'   },
  { key: 'whisper_wind',  name: 'Whisper Wind',  glyph: '♪',  role: 'Voice Synthesis',     accent: 'emerald'},
  { key: 'iron_crown',    name: 'Iron Crown',    glyph: '♛',  role: 'Hardware Sovereign',  accent: 'gold'   },
  { key: 'chronos',       name: 'Chronos',       glyph: '⧖',  role: 'Temporal Warden',     accent: 'violet' },
  { key: 'data_drake',    name: 'Data Drake',    glyph: '☷',  role: 'Data Oracle',         accent: 'emerald'},
];

type DaemonStatus = Record<string, any>;

export default function DaemonGrid() {
  const [status, setStatus] = useState<DaemonStatus>({});
  const [selected, setSelected] = useState<DaemonDef | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const s = await api.daemonsStatus();
      if (!alive) return;
      setStatus(s?.daemons || s || {});
    };
    load();
    const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <>
      <div className="daemon-grid">
        {DAEMONS.map((d) => {
          const entry = status?.[d.key] || {};
          const online = Boolean(
            entry.active ||
            entry.online ||
            entry.status === 'online' ||
            entry.status === 'running'
          );
          return (
            <button
              key={d.key}
              type="button"
              className={`daemon-cell d-${d.accent} ${online ? 'online' : ''}`}
              onClick={() => setSelected(d)}
              title={`${d.name} — click to open commands`}
            >
              <div className="daemon-glyph">{d.glyph}</div>
              <div className="daemon-meta">
                <div className="daemon-name">{d.name}</div>
                <div className="daemon-role">{d.role}</div>
              </div>
              <div className={`daemon-led ${online ? 'on' : ''}`} />
            </button>
          );
        })}
      </div>
      <DaemonCommandDrawer daemon={selected} onClose={() => setSelected(null)} />
    </>
  );
}
