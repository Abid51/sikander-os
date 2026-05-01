import { useEffect, useRef } from 'react';

type Props = {
  size?: number;
  label?: string;
};

/**
 * Tilted slatted orbit ring — inspired by the Iron Man HUD centerpiece.
 * Luminescent white-cyan band with internal segments, atmospheric glow,
 * slow axial rotation. Pure SVG + CSS.
 */
export default function OrbitRing({ size = 300, label }: Props) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    let t = 0, raf = 0;
    const tick = () => {
      t += 0.004;
      el.style.setProperty('--orbit-flicker', String(0.82 + Math.sin(t) * 0.08));
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, []);

  const slats = 64;

  return (
    <div
      ref={rootRef}
      className="orbit-ring"
      style={{ width: size, height: size, ['--orbit-size' as any]: `${size}px` }}
    >
      <div className="orbit-haze" />
      <div className="orbit-shaft" />

      <svg viewBox="0 0 200 200" className="orbit-svg">
        <defs>
          <radialGradient id="ringGlowR" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#ffffff" stopOpacity="0" />
            <stop offset="55%" stopColor="#8be8ff" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#001024" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="slatGrad" x1="0" x2="1">
            <stop offset="0%"  stopColor="#c2efff" stopOpacity="0" />
            <stop offset="30%" stopColor="#e8f9ff" stopOpacity="0.9" />
            <stop offset="50%" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="70%" stopColor="#e8f9ff" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#c2efff" stopOpacity="0" />
          </linearGradient>
        </defs>

        <circle cx="100" cy="100" r="95" fill="url(#ringGlowR)" />

        {/* Tilted ring group — rotateX via transform gives the elliptic read */}
        <g className="orbit-group" transform="translate(100 100)">
          {/* Outer thin rim */}
          <ellipse
            cx="0" cy="0" rx="82" ry="18"
            fill="none" stroke="#c2efff" strokeOpacity="0.25" strokeWidth="0.4"
          />
          <ellipse
            cx="0" cy="0" rx="76" ry="15"
            fill="none" stroke="#e8f9ff" strokeOpacity="0.35" strokeWidth="0.4"
          />

          {/* Slats — radial lines inside the ellipse band */}
          <g className="orbit-slats">
            {Array.from({ length: slats }, (_, i) => {
              const a = (i / slats) * Math.PI * 2;
              const x1 = Math.cos(a) * 76;
              const y1 = Math.sin(a) * 15;
              const x2 = Math.cos(a) * 82;
              const y2 = Math.sin(a) * 18;
              return (
                <line
                  key={i}
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke="url(#slatGrad)"
                  strokeWidth="0.8"
                  strokeLinecap="round"
                />
              );
            })}
          </g>

          {/* Moving highlight — a pair of bright arcs */}
          <g className="orbit-highlight">
            <ellipse
              cx="0" cy="0" rx="79" ry="16.5"
              fill="none"
              stroke="#ffffff"
              strokeOpacity="0.9"
              strokeWidth="1"
              strokeDasharray="18 380"
              strokeLinecap="round"
            />
          </g>
        </g>
      </svg>

      {label && <div className="orbit-label">{label}</div>}
    </div>
  );
}
