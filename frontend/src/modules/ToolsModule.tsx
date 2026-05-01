import { useState } from 'react';
import { api } from '../api';

type Mode = 'search' | 'calc' | 'code';

export default function ToolsModule() {
  const [mode, setMode] = useState<Mode>('search');
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<any>(null);

  const run = async () => {
    const q = input.trim();
    if (!q || busy) return;
    setBusy(true);
    setOut(null);
    let r: any = null;
    if (mode === 'search') r = await api.webSearch(q);
    if (mode === 'calc')   r = await api.calculate(q);
    if (mode === 'code')   r = await api.codeRun(q, 'python');
    setOut(r);
    setBusy(false);
  };

  return (
    <div className="tools-module">
      <div className="tm-modes">
        {(['search', 'calc', 'code'] as Mode[]).map((m) => (
          <button
            key={m}
            className={`tm-mode ${mode === m ? 'active' : ''}`}
            onClick={() => setMode(m)}
          >
            {m === 'search' ? '◉ WEB' : m === 'calc' ? 'Σ CALC' : '‹/› CODE'}
          </button>
        ))}
      </div>

      <div className="tm-input-row">
        {mode === 'code' ? (
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={'# Python\nprint("hello from IGRIS")'}
            rows={4}
            className="tm-code"
          />
        ) : (
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder={
              mode === 'search'
                ? 'Web search query…'
                : 'Expression e.g. 2*pi*4 + sqrt(49)'
            }
          />
        )}
        <button onClick={run} disabled={busy || !input.trim()}>
          {busy ? 'RUN…' : 'EXECUTE'}
        </button>
      </div>

      <div className="tm-out">
        <div className="tm-out-head">OUTPUT</div>
        {out == null && <div className="tm-empty">— awaiting execution —</div>}
        {out && mode === 'search' && (Array.isArray(out?.results) ? out.results : []).map((r: any, i: number) => (
          <a
            key={i}
            className="tm-result"
            href={r?.url || '#'}
            target="_blank"
            rel="noreferrer noopener"
          >
            <div className="tm-r-title">{r?.title || r?.url}</div>
            <div className="tm-r-snip">{r?.snippet || r?.description || ''}</div>
            <div className="tm-r-url">{r?.url}</div>
          </a>
        ))}
        {out && mode === 'calc' && (
          <pre className="tm-raw">{
            out?.result !== undefined
              ? `${out.result}`
              : JSON.stringify(out, null, 2)
          }</pre>
        )}
        {out && mode === 'code' && (
          <pre className="tm-raw">{
            out?.stdout || out?.output || JSON.stringify(out, null, 2)
          }</pre>
        )}
        {out && mode === 'search' && !Array.isArray(out?.results) && (
          <pre className="tm-raw">{JSON.stringify(out, null, 2)}</pre>
        )}
      </div>
    </div>
  );
}
