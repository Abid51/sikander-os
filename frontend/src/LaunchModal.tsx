import { useState } from 'react';
import { api } from './api';

type Action = {
  id: string;
  group: string;
  label: string;
  desc: string;
  run: () => Promise<any>;
};

const ACTIONS: Action[] = [
  { id: 'health',    group: 'CORE',     label: 'Health check',      desc: 'Ping backend',                  run: () => api.health() },
  { id: 'snapshot',  group: 'CORE',     label: 'System snapshot',   desc: 'Observability state',           run: () => api.snapshot() },
  { id: 'supremacy', group: 'CORE',     label: 'Igris supremacy',   desc: 'Awareness + power level',       run: () => api.supremacy() },

  { id: 'threats',   group: 'SECURITY', label: 'Scan threats',      desc: 'Blood Ward intel',              run: () => api.bloodWardThreats() },
  { id: 'lockdown',  group: 'SECURITY', label: 'Lockdown status',   desc: 'Current shield level',          run: () => api.lockdownStats() },
  { id: 'l2',        group: 'SECURITY', label: 'Engage lockdown L2',desc: 'Manual trigger',                run: () => api.lockdownEngage(2, 'Launcher') },

  { id: 'fg',        group: 'ECONOMY',  label: 'Fear & Greed',      desc: 'Market sentiment',              run: () => api.fearGreed() },
  { id: 'pf',        group: 'ECONOMY',  label: 'Portfolio',         desc: 'Current holdings',              run: () => api.portfolio() },

  { id: 'cap',       group: 'VISION',   label: 'Capture screen',    desc: 'Aether Eye snapshot',           run: () => api.captureScreen() },
  { id: 'ocr',       group: 'VISION',   label: 'OCR screen',        desc: 'Read on-screen text',           run: () => api.ocrScreen() },

  { id: 'mem',       group: 'MEMORY',   label: 'Memory stats',      desc: 'Neural vectors',                run: () => api.memoryStats() },
  { id: 'akr',       group: 'MEMORY',   label: 'Akashic recent',    desc: 'Latest records',                run: () => api.akashicRecent() },

  { id: 'dream',     group: 'COGNITION',label: 'Dream report',      desc: 'Latest idle cycle',             run: () => api.dreamReport() },
  { id: 'predict',   group: 'COGNITION',label: 'Prediction',        desc: 'Next likely action',            run: () => api.predictNow() },
];

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function LaunchModal({ open, onClose }: Props) {
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<{ title: string; data: any } | null>(null);

  if (!open) return null;

  const run = async (a: Action) => {
    setRunning(a.id);
    const r = await a.run();
    setRunning(null);
    setResult({ title: a.label, data: r });
  };

  const groups: Record<string, Action[]> = {};
  ACTIONS.forEach((a) => { (groups[a.group] ||= []).push(a); });

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal-card launch-card" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <h2>Launch</h2>
          <button className="modal-x" onClick={onClose}>✕</button>
        </header>
        <div className="modal-body launch-body">
          <div className="launch-grid">
            {Object.entries(groups).map(([g, items]) => (
              <div key={g} className="launch-group">
                <div className="launch-group-label">{g}</div>
                {items.map((a) => (
                  <button
                    key={a.id}
                    className="launch-action"
                    disabled={running !== null}
                    onClick={() => run(a)}
                  >
                    <span className="la-label">
                      {running === a.id ? 'Running…' : a.label}
                    </span>
                    <span className="la-desc">{a.desc}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>

          <div className="launch-result">
            <div className="lr-head">{result?.title || 'OUTPUT'}</div>
            <pre className="lr-body">
              {result ? JSON.stringify(result.data, null, 2) : '— run an action —'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
