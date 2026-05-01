import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api';

export type PaletteAction = {
  id: string;
  group: string;
  label: string;
  hint?: string;
  run: () => Promise<void> | void;
};

type Props = {
  open: boolean;
  onClose: () => void;
  onResult: (title: string, body?: any) => void;
};

/**
 * Spotlight / JARVIS command palette. Triggered via Ctrl/Cmd+K.
 * Exposes the most interactive IGRIS endpoints as searchable actions.
 */
export default function CommandPalette({ open, onClose, onResult }: Props) {
  const [query, setQuery] = useState('');
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const actions = useMemo<PaletteAction[]>(() => {
    const wrap = (title: string, fn: () => Promise<any> | any) => async () => {
      const data = await fn();
      onResult(title, data);
    };
    return [
      // Core
      { id: 'ping', group: 'CORE',     label: 'Ping health',         hint: 'GET /health',                 run: wrap('HEALTH', api.health) },
      { id: 'sup',  group: 'CORE',     label: 'IGRIS supremacy',     hint: 'GET /igris/supremacy',        run: wrap('SUPREMACY', api.supremacy) },
      { id: 'god',  group: 'CORE',     label: 'IGRIS god-mode',      hint: 'GET /igris/god-mode',         run: wrap('GOD-MODE', api.godMode) },
      { id: 'omg',  group: 'CORE',     label: 'IGRIS omega',         hint: 'GET /igris/omega',            run: wrap('OMEGA', api.omega) },

      // Daemons
      { id: 'dstat',group: 'DAEMONS',  label: 'Daemon status',       hint: 'GET /daemons/status',         run: wrap('DAEMONS', api.daemonsStatus) },
      { id: 'blood',group: 'DAEMONS',  label: 'Blood Ward threats',  hint: 'GET /daemons/blood_ward/threats', run: wrap('THREATS', api.bloodWardThreats) },

      // Security
      { id: 'lock', group: 'SECURITY', label: 'Lockdown stats',      hint: 'GET /lockdown/stats',         run: wrap('LOCKDOWN', api.lockdownStats) },
      { id: 'l1',   group: 'SECURITY', label: 'Engage Lockdown L1',  hint: 'POST /lockdown/engage',       run: wrap('LOCKDOWN→L1', () => api.lockdownEngage(1, 'Palette trigger')) },
      { id: 'l2',   group: 'SECURITY', label: 'Engage Lockdown L2',  hint: 'POST /lockdown/engage',       run: wrap('LOCKDOWN→L2', () => api.lockdownEngage(2, 'Palette trigger')) },
      { id: 'l3',   group: 'SECURITY', label: 'Engage Lockdown L3',  hint: 'POST /lockdown/engage',       run: wrap('LOCKDOWN→L3', () => api.lockdownEngage(3, 'Palette trigger')) },
      { id: 'dis',  group: 'SECURITY', label: 'Disengage Lockdown',  hint: 'POST /lockdown/disengage',    run: wrap('DISENGAGE', () => api.lockdownDisengage('')) },
      { id: 'sha',  group: 'SECURITY', label: 'Shadow Ops stats',    hint: 'GET /shadow/stats',           run: wrap('SHADOW', api.shadowStats) },

      // Economy
      { id: 'fg',   group: 'ECONOMY',  label: 'Fear & Greed',        hint: 'GET /economy/fear-greed',     run: wrap('FEAR/GREED', api.fearGreed) },
      { id: 'pf',   group: 'ECONOMY',  label: 'Portfolio',           hint: 'GET /economy/portfolio',      run: wrap('PORTFOLIO', api.portfolio) },

      // Vision
      { id: 'eye',  group: 'VISION',   label: 'Aether Eye status',   hint: 'GET /api/vision/aether-eye/status', run: wrap('AETHER EYE', api.aetherStatus) },
      { id: 'cap',  group: 'VISION',   label: 'Capture screen',      hint: 'POST /api/vision/screen/capture', run: wrap('CAPTURE', api.captureScreen) },
      { id: 'ocr',  group: 'VISION',   label: 'OCR screen',          hint: 'POST /api/vision/ocr/screen',     run: wrap('OCR', api.ocrScreen) },

      // Memory
      { id: 'mem',  group: 'MEMORY',   label: 'Memory stats',        hint: 'GET /memory/stats',           run: wrap('MEMORY', api.memoryStats) },
      { id: 'akr',  group: 'MEMORY',   label: 'Akashic recent',      hint: 'GET /akashic/recent',         run: wrap('AKASHIC', api.akashicRecent) },
      { id: 'grp',  group: 'MEMORY',   label: 'Knowledge graph',     hint: 'GET /graph/stats',            run: wrap('GRAPH', api.graphStats) },

      // Quantum / Cognition
      { id: 'qa',   group: 'QUANTUM',  label: 'Quantum angles',      hint: 'GET /quantum/angles',         run: wrap('ANGLES', api.quantumAngles) },

      // Persona / emotion
      { id: 'emo',  group: 'SELF',     label: 'Current emotion',     hint: 'GET /emotion/current',        run: wrap('EMOTION', api.emotionCurrent) },
      { id: 'per',  group: 'SELF',     label: 'Persona stats',       hint: 'GET /persona/stats',          run: wrap('PERSONA', api.personaStats) },
      { id: 'drm',  group: 'SELF',     label: 'Dream report',        hint: 'GET /dream/report',           run: wrap('DREAM', api.dreamReport) },
      { id: 'pre',  group: 'SELF',     label: 'Prediction now',      hint: 'GET /predict/now',            run: wrap('PREDICT', api.predictNow) },

      // System
      { id: 'ss',   group: 'SYSTEM',   label: 'System stats',        hint: 'GET /system/stats',           run: wrap('SYSTEM', api.systemStats) },
      { id: 'mh',   group: 'SYSTEM',   label: 'Monitor health',      hint: 'GET /monitor/health-detailed',run: wrap('MON HEALTH', api.monitorHealthDetailed) },
      { id: 'obs',  group: 'SYSTEM',   label: 'Observability snap',  hint: 'GET /observability/snapshot', run: wrap('SNAPSHOT', api.snapshot) },
    ];
  }, [onResult]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter((a) =>
      a.label.toLowerCase().includes(q) ||
      a.group.toLowerCase().includes(q) ||
      (a.hint || '').toLowerCase().includes(q)
    );
  }, [actions, query]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSel(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  useEffect(() => { setSel(0); }, [query]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(filtered.length - 1, s + 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
    if (e.key === 'Enter' && filtered[sel]) {
      e.preventDefault();
      filtered[sel].run();
      onClose();
    }
    if (e.key === 'Escape') onClose();
  };

  if (!open) return null;

  // Group for display
  const groups: Record<string, PaletteAction[]> = {};
  filtered.forEach((a) => { (groups[a.group] ||= []).push(a); });
  let runningIdx = 0;

  return (
    <div className="cmd-palette" onClick={onClose}>
      <div className="cmd-palette-inner" onClick={(e) => e.stopPropagation()}>
        <div className="cmd-head">
          <span className="cmd-prompt">» IGRIS</span>
          <input
            ref={inputRef}
            className="cmd-input"
            placeholder="Type a command, daemon, or module…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
          />
          <kbd>ESC</kbd>
        </div>
        <div className="cmd-list">
          {Object.entries(groups).map(([grp, items]) => (
            <div key={grp} className="cmd-group">
              <div className="cmd-group-head">{grp}</div>
              {items.map((a) => {
                const idx = runningIdx++;
                const active = idx === sel;
                return (
                  <button
                    key={a.id}
                    className={`cmd-item ${active ? 'active' : ''}`}
                    onMouseEnter={() => setSel(idx)}
                    onClick={() => { a.run(); onClose(); }}
                  >
                    <span className="cmd-label">{a.label}</span>
                    {a.hint && <span className="cmd-hint">{a.hint}</span>}
                  </button>
                );
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="cmd-empty">No actions match "{query}".</div>
          )}
        </div>
        <div className="cmd-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> run</span>
          <span><kbd>Esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
