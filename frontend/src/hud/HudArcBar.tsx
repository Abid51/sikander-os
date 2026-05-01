type Props = {
  level: number;      // 0-100
  label?: string;
  tone?: 'cyan' | 'gold' | 'crimson';
};

/**
 * Horizontal arc bar (think HUD weapon charge / shield level).
 */
export default function HudArcBar({ level, label, tone = 'cyan' }: Props) {
  const v = Math.max(0, Math.min(100, level));
  const segs = 20;
  const active = Math.round((v / 100) * segs);

  return (
    <div className={`hud-arc-bar tone-${tone}`}>
      {label && <div className="hud-arc-label">{label}</div>}
      <div className="hud-arc-track">
        {Array.from({ length: segs }, (_, i) => (
          <span
            key={i}
            className={`hud-arc-seg ${i < active ? 'on' : ''}`}
            style={{ transform: `skewX(-22deg)` }}
          />
        ))}
      </div>
      <div className="hud-arc-readout">{v.toFixed(0)}%</div>
    </div>
  );
}
