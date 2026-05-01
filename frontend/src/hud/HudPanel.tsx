import { type CSSProperties, type ReactNode } from 'react';
import { useLayout } from '../ThemeLayout';

type HudPanelProps = {
  /** Unique ID for layout persistence (minimize state). */
  id?: string;
  title?: string;
  subtitle?: string;
  corner?: 'tl' | 'tr' | 'bl' | 'br' | 'all' | 'none';
  accent?: 'cyan' | 'gold' | 'crimson' | 'violet' | 'emerald';
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  status?: string;
  actions?: ReactNode;
  dense?: boolean;
  /** Disable the minimize button on this panel. */
  noCollapse?: boolean;
};

export default function HudPanel({
  id,
  title,
  subtitle,
  corner = 'all',
  accent = 'cyan',
  children,
  className = '',
  style,
  status,
  actions,
  dense = false,
  noCollapse,
}: HudPanelProps) {
  const layout = useLayout();
  const min = id ? layout.isMinimized(id) : false;

  const cls = [
    'hud-panel',
    `accent-${accent}`,
    `corner-${corner}`,
    dense ? 'hud-panel-dense' : '',
    min ? 'hud-panel-minimized' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <section className={cls} style={style}>
      <div className="hud-panel-frame" aria-hidden />
      <div className="hud-panel-corner tl" aria-hidden />
      <div className="hud-panel-corner tr" aria-hidden />
      <div className="hud-panel-corner bl" aria-hidden />
      <div className="hud-panel-corner br" aria-hidden />

      {(title || actions || status || id) && (
        <header className="hud-panel-head">
          <div className="hud-panel-title-wrap">
            {title && <h3 className="hud-panel-title">{title}</h3>}
            {subtitle && !min && <span className="hud-panel-subtitle">{subtitle}</span>}
          </div>
          <div className="hud-panel-meta">
            {status && !min && <span className={`hud-status hud-status-${accent}`}>{status}</span>}
            {actions && !min}
            {actions && !min && actions}
            {id && !noCollapse && (
              <button
                className="hud-panel-collapse"
                onClick={() => layout.toggle(id)}
                title={min ? 'Expand' : 'Collapse'}
                aria-label={min ? 'Expand panel' : 'Collapse panel'}
              >
                {min ? '+' : '—'}
              </button>
            )}
          </div>
        </header>
      )}

      {!min && <div className="hud-panel-body">{children}</div>}
    </section>
  );
}
