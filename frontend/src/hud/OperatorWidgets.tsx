import { useEffect, useState, type ReactNode } from 'react';

/**
 * Operator-style widgets inspired by tactical / surveillance dashboards.
 * All flat, monochrome, small type, yellow-on-black when OPERATOR theme is on.
 */

// ────────────────────────── Operator card ───────────────────────────────

export function OperatorCard({
  name,
  role,
  status = 'ACTIVE',
  initials,
  right,
}: {
  name: string;
  role: string;
  status?: string;
  initials?: string;
  right?: ReactNode;
}) {
  const init = initials || name.split(' ').map((s) => s[0]).slice(0, 2).join('').toUpperCase();
  return (
    <div className="op-card">
      <div className="op-avatar">
        <span>{init}</span>
        <i className={`op-led op-${status.toLowerCase()}`} />
      </div>
      <div className="op-meta">
        <div className="op-name">{name}</div>
        <div className="op-role">{role}</div>
      </div>
      <div className="op-right">
        {right ?? <span className="op-status">{status}</span>}
      </div>
    </div>
  );
}

// ────────────────────────── Mini World Map ──────────────────────────────

const PINS = [
  { x: 22, y: 42, label: 'LA'  },
  { x: 47, y: 38, label: 'NYC' },
  { x: 48, y: 33, label: 'LON' },
  { x: 55, y: 42, label: 'IST' },
  { x: 63, y: 50, label: 'DXB' },
  { x: 72, y: 55, label: 'MUM' },
  { x: 81, y: 55, label: 'TKY' },
];

export function MiniMap() {
  const [active, setActive] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setActive((a) => (a + 1) % PINS.length), 2500);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="mini-map">
      <svg viewBox="0 0 200 100" preserveAspectRatio="xMidYMid meet">
        {/* Simple world outline — stylised landmass blobs */}
        <g className="mm-land" fill="currentColor" opacity="0.18">
          <path d="M18 28 Q34 20, 50 26 L52 34 L46 42 L36 44 L22 40 Z" />
          <path d="M55 52 Q60 60, 70 62 L70 70 L62 72 L54 68 Z" />
          <path d="M60 22 Q72 18, 90 24 Q110 22, 130 28 L132 40 Q118 44, 100 42 Q82 44, 62 38 Z" />
          <path d="M95 56 Q105 54, 118 58 L118 66 L104 66 L96 62 Z" />
          <path d="M140 30 Q156 26, 170 32 L176 44 Q164 50, 150 46 L140 40 Z" />
          <path d="M172 60 Q180 58, 188 62 L188 70 L178 70 Z" />
        </g>

        {/* Grid */}
        <g className="mm-grid" stroke="currentColor" strokeOpacity="0.08" strokeWidth="0.2">
          {Array.from({ length: 11 }, (_, i) => (
            <line key={`v${i}`} x1={i * 20} y1="0" x2={i * 20} y2="100" />
          ))}
          {Array.from({ length: 6 }, (_, i) => (
            <line key={`h${i}`} x1="0" y1={i * 20} x2="200" y2={i * 20} />
          ))}
        </g>

        {/* Pins */}
        {PINS.map((p, i) => (
          <g key={p.label} transform={`translate(${p.x * 2} ${p.y})`}>
            <circle r={i === active ? 3 : 1.4} fill="currentColor" />
            {i === active && (
              <>
                <circle r="5" fill="none" stroke="currentColor" strokeWidth="0.5" className="mm-ping" />
                <text x="6" y="2" fontSize="4" fill="currentColor" opacity="0.9">{p.label}</text>
              </>
            )}
          </g>
        ))}
      </svg>
      <div className="mini-map-legend">
        <span>NODES · {PINS.length}</span>
        <span>ACTIVE · {PINS[active].label}</span>
      </div>
    </div>
  );
}

// ────────────────────────── Timeline Strip ─────────────────────────────

export function TimelineStrip({
  marks = [10, 24, 38, 52, 68, 84],
  cursor = 55,
}: {
  marks?: number[];
  cursor?: number;
}) {
  return (
    <div className="timeline-strip">
      <div className="ts-track">
        {Array.from({ length: 60 }, (_, i) => (
          <span key={i} className={`ts-tick ${i % 10 === 0 ? 'major' : ''}`} />
        ))}
        {marks.map((m, i) => (
          <span key={`m${i}`} className="ts-event" style={{ left: `${m}%` }} title={`T+${m}`} />
        ))}
        <span className="ts-cursor" style={{ left: `${cursor}%` }} />
      </div>
      <div className="ts-labels">
        <span>T-00</span><span>T+30</span><span>T+60</span>
      </div>
    </div>
  );
}

// ────────────────────────── Waveform ───────────────────────────────────

export function Waveform({ bars = 40 }: { bars?: number }) {
  const [vals, setVals] = useState<number[]>(() =>
    Array.from({ length: bars }, () => Math.random() * 0.6 + 0.1)
  );
  useEffect(() => {
    const t = setInterval(() => {
      setVals(Array.from({ length: bars }, () => Math.random() * 0.85 + 0.1));
    }, 380);
    return () => clearInterval(t);
  }, [bars]);
  return (
    <div className="waveform">
      {vals.map((v, i) => (
        <span key={i} style={{ height: `${v * 100}%` }} />
      ))}
    </div>
  );
}

// ────────────────────────── Data Table ─────────────────────────────────

export function DataTable<T>({
  rows,
  cols,
  emptyText = '— no data —',
}: {
  rows: T[];
  cols: { key: string; label: string; get: (r: T) => ReactNode; w?: string }[];
  emptyText?: string;
}) {
  return (
    <div className="data-table">
      <div className="dt-head">
        {cols.map((c) => (
          <span key={c.key} style={{ flex: c.w || '1' }}>{c.label}</span>
        ))}
      </div>
      <div className="dt-body">
        {rows.length === 0 && <div className="dt-empty">{emptyText}</div>}
        {rows.map((r, i) => (
          <div key={i} className="dt-row">
            {cols.map((c) => (
              <span key={c.key} style={{ flex: c.w || '1' }}>{c.get(r)}</span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ────────────────────────── Status Strip ───────────────────────────────

export function StatusStrip({
  items,
}: {
  items: { label: string; value: ReactNode; tone?: 'ok' | 'warn' | 'alert' | 'info' }[];
}) {
  return (
    <div className="status-strip">
      {items.map((it, i) => (
        <div key={i} className={`ss-item ss-${it.tone || 'info'}`}>
          <span className="ss-label">{it.label}</span>
          <span className="ss-value">{it.value}</span>
        </div>
      ))}
    </div>
  );
}

// ────────────────────────── ID Card ────────────────────────────────────

export function IdCard({
  name,
  code,
  rank,
  initials,
}: {
  name: string;
  code: string;
  rank: string;
  initials?: string;
}) {
  const init = initials || name.split(' ').map((s) => s[0]).slice(0, 2).join('').toUpperCase();
  return (
    <div className="id-card">
      <div className="id-avatar">
        <span>{init}</span>
      </div>
      <div className="id-body">
        <div className="id-name">{name}</div>
        <div className="id-kv"><span>ID</span><b>{code}</b></div>
        <div className="id-kv"><span>RANK</span><b>{rank}</b></div>
        <div className="id-kv"><span>CLEAR</span><b className="yellow">LEVEL-A / OMEGA</b></div>
      </div>
    </div>
  );
}
