import { useEffect, useRef } from 'react';

type Props = {
  size?: number;
  pulse?: boolean;
  label?: string;
};

/**
 * JARVIS/Iron-Man arc reactor with rotating rings, core glow and
 * subtle rotation. Pure CSS/SVG — no libs, no assets.
 */
export default function ArcReactor({ size = 220, pulse = true, label }: Props) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  // gentle hue breathing
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    let t = 0;
    let raf = 0;
    const tick = () => {
      t += 0.008;
      const hue = 185 + Math.sin(t) * 6;
      el.style.setProperty('--reactor-hue', String(hue));
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, []);

  const s = size;

  return (
    <div
      ref={rootRef}
      className={`arc-reactor ${pulse ? 'pulse' : ''}`}
      style={{ width: s, height: s, ['--reactor-size' as any]: `${s}px` }}
    >
      <svg viewBox="0 0 200 200" className="arc-svg">
        <defs>
          <radialGradient id="coreGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#e8f9ff" stopOpacity="1" />
            <stop offset="35%" stopColor="#7ddcff" stopOpacity="0.95" />
            <stop offset="70%" stopColor="#1a6aa6" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#001020" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="ringGrad" x1="0" x2="1">
            <stop offset="0%"  stopColor="#5adfff" />
            <stop offset="50%" stopColor="#7ddcff" />
            <stop offset="100%" stopColor="#afeaff" />
          </linearGradient>
          <linearGradient id="goldGrad" x1="0" x2="1">
            <stop offset="0%"  stopColor="#f4c26b" />
            <stop offset="50%" stopColor="#ffd86b" />
            <stop offset="100%" stopColor="#fff3c7" />
          </linearGradient>
        </defs>

        {/* core */}
        <circle cx="100" cy="100" r="22" fill="url(#coreGrad)" />
        <circle cx="100" cy="100" r="10" fill="#e8f9ff" opacity="0.85" />

        {/* inner ring (8 segments) */}
        <g className="arc-ring inner">
          {Array.from({ length: 8 }, (_, i) => {
            const a1 = (i * 360) / 8 + 4;
            const a2 = a1 + (360 / 8) - 8;
            return (
              <path
                key={i}
                d={describeArc(100, 100, 38, a1, a2)}
                stroke="url(#ringGrad)"
                strokeWidth="5"
                fill="none"
                strokeLinecap="round"
              />
            );
          })}
        </g>

        {/* middle ring (12 segments, thinner) */}
        <g className="arc-ring middle">
          {Array.from({ length: 12 }, (_, i) => {
            const a1 = (i * 360) / 12 + 3;
            const a2 = a1 + (360 / 12) - 6;
            return (
              <path
                key={i}
                d={describeArc(100, 100, 56, a1, a2)}
                stroke="#5adfff"
                strokeOpacity="0.85"
                strokeWidth="2"
                fill="none"
                strokeLinecap="round"
              />
            );
          })}
        </g>

        {/* outer gold accent */}
        <g className="arc-ring outer">
          {Array.from({ length: 6 }, (_, i) => {
            const a1 = (i * 360) / 6 + 2;
            const a2 = a1 + (360 / 6) - 4;
            return (
              <path
                key={i}
                d={describeArc(100, 100, 78, a1, a2)}
                stroke="url(#goldGrad)"
                strokeOpacity="0.75"
                strokeWidth="1.5"
                fill="none"
                strokeLinecap="round"
              />
            );
          })}
        </g>

        {/* ticks */}
        <g className="arc-ticks">
          {Array.from({ length: 60 }, (_, i) => {
            const ang = (i * 360) / 60;
            const r1 = 90, r2 = i % 5 === 0 ? 94 : 92;
            const [x1, y1] = polar(100, 100, r1, ang);
            const [x2, y2] = polar(100, 100, r2, ang);
            return (
              <line
                key={i}
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke="#5adfff"
                strokeOpacity={i % 5 === 0 ? 0.7 : 0.35}
                strokeWidth="1"
              />
            );
          })}
        </g>
      </svg>

      {label && <div className="arc-label">{label}</div>}
    </div>
  );
}

function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

function describeArc(cx: number, cy: number, r: number, a1: number, a2: number): string {
  const [x1, y1] = polar(cx, cy, r, a1);
  const [x2, y2] = polar(cx, cy, r, a2);
  const large = a2 - a1 <= 180 ? 0 : 1;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
}
