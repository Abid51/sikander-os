import { useEffect, useState } from 'react';
import { api } from '../api';

type Angle = { id?: string; name?: string; label?: string; description?: string };

export default function QuantumModule() {
  const [angles, setAngles] = useState<Angle[]>([]);
  const [angle, setAngle] = useState<string>('');
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    (async () => {
      const a = await api.quantumAngles();
      if (!alive) return;
      const list = (a?.angles ?? a?.items ?? a ?? []) as Angle[];
      setAngles(Array.isArray(list) ? list : []);
    })();
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => setTick((v) => v + 1), 90);
    return () => clearInterval(t);
  }, [busy]);

  const run = async () => {
    const q = prompt.trim();
    if (!q || busy) return;
    setBusy(true);
    setResult(null);
    const r = await api.quantumQuickThink(q, angle || undefined);
    setResult(r);
    setBusy(false);
  };

  const answer =
    result?.answer ??
    result?.response ??
    result?.text ??
    result?.output ??
    (result ? JSON.stringify(result, null, 2) : '');

  return (
    <div className="quantum-module">
      <div className="qm-header">
        <span className="qm-title">QUANTUM THINK</span>
        <span className="qm-sub">superpositional reasoning · /quantum/quick-think</span>
      </div>

      <div className="qm-angles">
        <button
          type="button"
          className={`qm-angle ${angle === '' ? 'active' : ''}`}
          onClick={() => setAngle('')}
        >
          ⚛ AUTO
        </button>
        {angles.slice(0, 10).map((a, i) => {
          const id = a.id || a.name || a.label || `angle-${i}`;
          return (
            <button
              key={id}
              type="button"
              className={`qm-angle ${angle === id ? 'active' : ''}`}
              title={a.description || id}
              onClick={() => setAngle(id)}
            >
              {id.toUpperCase().slice(0, 14)}
            </button>
          );
        })}
      </div>

      <div className="qm-input">
        <textarea
          placeholder="Pose a question for multi-angle quantum reasoning…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run(); }}
          rows={3}
        />
        <button onClick={run} disabled={busy || !prompt.trim()}>
          {busy ? 'COLLAPSING…' : 'COLLAPSE WAVE'}
        </button>
      </div>

      <div className="qm-result">
        <div className="qm-result-head">
          <span>OUTPUT</span>
          <span className={`qm-state ${busy ? 'busy' : ''}`}>
            {busy ? `⚛ superposition · ${tick}` : result ? '⚛ collapsed' : '⚛ idle'}
          </span>
        </div>
        <div className="qm-result-body">
          {busy && (
            <div className="qm-scan">
              {[0,1,2,3,4,5,6,7].map((i) => (
                <span key={i} style={{ animationDelay: `${i * 0.1}s` }} />
              ))}
            </div>
          )}
          {!busy && answer && <pre className="qm-ans">{String(answer)}</pre>}
          {!busy && !answer && <div className="qm-empty">— awaiting query —</div>}
        </div>
      </div>
    </div>
  );
}
