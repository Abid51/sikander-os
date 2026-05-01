type Props = {
  value: number;         // 0..100
  label: string;
  unit?: string;
  size?: number;
  accent?: 'cyan' | 'gold' | 'crimson' | 'emerald' | 'violet';
};

/**
 * Radial gauge used for CPU/Memory/Disk/Temp and other 0-100 metrics.
 * Draws background track + value arc with cap knob.
 */
export default function CircularGauge({
  value,
  label,
  unit = '%',
  size = 92,
  accent = 'cyan',
}: Props) {
  const v = Math.max(0, Math.min(100, value));
  const r = 42;
  const c = 2 * Math.PI * r;
  const dash = (v / 100) * c;

  return (
    <div className={`gauge gauge-${accent}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100">
        <circle
          cx="50" cy="50" r={r}
          className="gauge-track"
          fill="none"
          strokeWidth="6"
        />
        <circle
          cx="50" cy="50" r={r}
          className="gauge-value"
          fill="none"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
          transform="rotate(-90 50 50)"
        />
      </svg>
      <div className="gauge-center">
        <div className="gauge-num">
          {Math.round(v)}
          <span className="gauge-unit">{unit}</span>
        </div>
        <div className="gauge-label">{label}</div>
      </div>
    </div>
  );
}
