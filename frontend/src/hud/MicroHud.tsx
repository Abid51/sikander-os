import { useEffect, useRef, useState } from 'react';

/**
 * Screen-corner HUD brackets with live coordinates.
 * Absolutely positioned at viewport corners; pointer-events none.
 */
export function CornerBrackets() {
  const [mx, setMx] = useState(0);
  const [my, setMy] = useState(0);

  useEffect(() => {
    const h = (e: MouseEvent) => { setMx(e.clientX); setMy(e.clientY); };
    window.addEventListener('mousemove', h);
    return () => window.removeEventListener('mousemove', h);
  }, []);

  const pad = (n: number) => n.toString().padStart(4, '0');

  return (
    <div className="corner-brackets" aria-hidden>
      <span className="cb cb-tl" />
      <span className="cb cb-tr" />
      <span className="cb cb-bl" />
      <span className="cb cb-br" />

      <div className="cb-coord cb-coord-tl">
        <span>LAT</span><b>{pad(mx)}</b><span>LON</span><b>{pad(my)}</b>
      </div>
      <div className="cb-coord cb-coord-tr">
        <span>SEC.HUD-07</span><b>OPERATIONAL</b>
      </div>
      <div className="cb-coord cb-coord-bl">
        <span>BUILD</span><b>MK-VII / 7.24</b>
      </div>
      <div className="cb-coord cb-coord-br">
        <span>GRID</span><b>N-37.21 / E-51.44</b>
      </div>
    </div>
  );
}

/**
 * Central targeting reticle (like JARVIS target-lock crosshair).
 * Rotates slowly, breathes, fades when interacting with forms.
 */
export function CenterReticle() {
  return (
    <div className="center-reticle" aria-hidden>
      <svg viewBox="0 0 120 120">
        <g fill="none" stroke="currentColor" strokeWidth="0.6">
          <circle cx="60" cy="60" r="56" />
          <circle cx="60" cy="60" r="44" strokeDasharray="2 4" />
          <circle cx="60" cy="60" r="28" opacity="0.5" />
          <line x1="60" y1="0"  x2="60" y2="18" />
          <line x1="60" y1="102" x2="60" y2="120" />
          <line x1="0"  y1="60" x2="18"  y2="60" />
          <line x1="102" y1="60" x2="120" y2="60" />
          <circle cx="60" cy="60" r="2" fill="currentColor" />
        </g>
      </svg>
    </div>
  );
}

/**
 * Tiny animated EKG line for the top bar. Pure CSS/SVG.
 */
export function Heartbeat({ bpm = 72 }: { bpm?: number }) {
  const ratio = 60 / bpm;
  return (
    <div className="heartbeat" title={`PULSE · ${bpm} BPM`}>
      <svg viewBox="0 0 120 24" preserveAspectRatio="none">
        <path
          d="M0 12 L14 12 L20 4 L26 20 L34 12 L50 12 L56 7 L62 17 L70 12 L90 12 L96 2 L102 22 L108 12 L120 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="heartbeat-num">{bpm}<i>BPM</i></span>
      <style>{`.heartbeat svg path { stroke-dasharray: 240; stroke-dashoffset: 240; animation: hb-scan ${ratio}s linear infinite; }
        @keyframes hb-scan { to { stroke-dashoffset: -240; } }`}</style>
    </div>
  );
}

/**
 * Vertical edge data-rail: slow upward-scrolling hex/binary/coords.
 * Purely decorative but sells the authentic "data everywhere" feel.
 */
export function MicroDataRail({ side }: { side: 'left' | 'right' }) {
  const lines = useRandomLines(48);
  return (
    <div className={`data-rail data-rail-${side}`} aria-hidden>
      <div className="data-rail-scroll">
        {lines.map((l, i) => <span key={i} className="dr-line">{l}</span>)}
        {lines.map((l, i) => <span key={`b${i}`} className="dr-line">{l}</span>)}
      </div>
    </div>
  );
}

function useRandomLines(count: number): string[] {
  const [lines, setLines] = useState<string[]>(() => generate(count));
  useEffect(() => {
    const t = setInterval(() => setLines(generate(count)), 7000);
    return () => clearInterval(t);
  }, [count]);
  return lines;
}

function generate(count: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const kind = Math.floor(Math.random() * 4);
    if (kind === 0) out.push(randHex(8) + ' · ' + randHex(4));
    else if (kind === 1) out.push('0x' + randHex(6));
    else if (kind === 2) out.push(Array.from({ length: 8 }, () => Math.random() > 0.5 ? '1' : '0').join(''));
    else out.push('Δ' + (Math.random() * 1000).toFixed(2));
  }
  return out;
}

function randHex(len: number): string {
  let s = '';
  for (let i = 0; i < len; i++) s += Math.floor(Math.random() * 16).toString(16).toUpperCase();
  return s;
}

/**
 * Inline sparkline for gauges. 20 rolling points.
 */
export function Sparkline({
  values,
  width = 70,
  height = 18,
  tone = 'cyan',
}: {
  values: number[];
  width?: number;
  height?: number;
  tone?: 'cyan' | 'gold' | 'emerald' | 'crimson' | 'violet';
}) {
  const pts = normalize(values, width, height);
  return (
    <svg className={`sparkline spark-${tone}`} viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={width - 1} cy={lastY(values, height)} r="1.8" fill="currentColor" />
    </svg>
  );
}

function normalize(values: number[], w: number, h: number): string {
  if (values.length < 2) return `0,${h / 2} ${w},${h / 2}`;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / span) * (h - 2) - 1;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

function lastY(values: number[], h: number): number {
  if (values.length === 0) return h / 2;
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  return h - ((values[values.length - 1] - min) / span) * (h - 2) - 1;
}

/**
 * Tiny rolling time-series store; call pushValue() on interval.
 */
export function useRollingSeries(max = 24, seedNoise = true) {
  const [values, setValues] = useState<number[]>(
    seedNoise ? Array.from({ length: max }, () => Math.random() * 50 + 25) : []
  );
  const push = (v: number) => setValues((cur) => [...cur.slice(-(max - 1)), v]);
  return { values, push };
}

/**
 * Compact clock with UTC + local; monospace.
 */
export function MiniClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const local = now.toLocaleTimeString('en-GB', { hour12: false });
  const utc = now.toUTCString().slice(17, 25);
  return (
    <div className="mini-clock">
      <div><span>LCL</span><b>{local}</b></div>
      <div><span>UTC</span><b>{utc}</b></div>
    </div>
  );
}

/** Frame-counter (FPS) sensor for the HUD — tiny perf indicator. */
export function FpsCounter() {
  const [fps, setFps] = useState(60);
  const raf = useRef(0);
  const last = useRef(performance.now());
  const frames = useRef(0);
  useEffect(() => {
    const tick = () => {
      frames.current += 1;
      const now = performance.now();
      if (now - last.current >= 1000) {
        setFps(frames.current);
        frames.current = 0;
        last.current = now;
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, []);
  return <span className="fps-counter" title={`${fps} fps`}>{fps}<i>fps</i></span>;
}
