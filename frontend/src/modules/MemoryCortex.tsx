import { useEffect, useState } from 'react';
import { api } from '../api';

function num(...candidates: any[]): number {
  for (const c of candidates) {
    if (typeof c === 'number') return c;
    if (typeof c === 'string' && !Number.isNaN(Number(c))) return Number(c);
  }
  return 0;
}

export default function MemoryCortex() {
  const [memory, setMemory] = useState<any>({});
  const [akashic, setAkashic] = useState<any>({});
  const [graph, setGraph] = useState<any>({});
  const [recent, setRecent] = useState<any[]>([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [m, a, g, r] = await Promise.all([
        api.memoryStats(),
        api.akashicStats(),
        api.graphStats(),
        api.akashicRecent(),
      ]);
      if (!alive) return;
      setMemory(m || {});
      setAkashic(a || {});
      setGraph(g || {});
      const list = r?.entries ?? r?.recent ?? r?.items ?? [];
      setRecent(Array.isArray(list) ? list.slice(0, 5) : []);
    };
    load();
    const t = setInterval(load, 12000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div className="memory-cortex">
      <div className="mc-grid">
        <div className="mc-cell">
          <div className="mc-label">NEURAL</div>
          <div className="mc-num">{num(memory.total, memory.count, memory.entries)}</div>
        </div>
        <div className="mc-cell">
          <div className="mc-label">AKASHIC</div>
          <div className="mc-num">{num(akashic.total, akashic.entries, akashic.records)}</div>
        </div>
        <div className="mc-cell">
          <div className="mc-label">GRAPH</div>
          <div className="mc-num">
            {num(graph.nodes)}<span className="mc-num-s"> / {num(graph.edges)}</span>
          </div>
        </div>
      </div>

      <div className="mc-recent">
        <div className="mcr-head">RECENT AKASHIC</div>
        {recent.length === 0 && <div className="mcr-empty">No recent entries.</div>}
        {recent.map((r, i) => (
          <div key={i} className="mcr-row">
            <span className="mcr-time">
              {r?.timestamp ? new Date(r.timestamp).toLocaleTimeString() : '—'}
            </span>
            <span className="mcr-msg">
              {String(r?.event || r?.text || r?.message || r?.content || '…').slice(0, 80)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
