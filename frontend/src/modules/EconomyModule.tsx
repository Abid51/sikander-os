import { useEffect, useState } from 'react';
import { api } from '../api';

type FearGreed = { value?: number; classification?: string; label?: string };

export default function EconomyModule() {
  const [fg, setFg] = useState<FearGreed>({});
  const [portfolio, setPortfolio] = useState<any>({});
  const [signal, setSignal] = useState<any>(null);
  const [symbol, setSymbol] = useState('BTC');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    const [f, p] = await Promise.all([api.fearGreed(), api.portfolio()]);
    setFg(f || {});
    setPortfolio(p || {});
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const analyse = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) return;
    setLoading(true);
    const s = await api.economySignal(sym);
    setSignal(s);
    setLoading(false);
  };

  const fgValue = Number(fg?.value ?? 50);
  const fgLabel = fg?.classification || fg?.label || classifyFG(fgValue);
  const total = portfolio?.total_value ?? portfolio?.total ?? 0;
  const holdings = portfolio?.holdings ?? portfolio?.positions ?? [];

  return (
    <div className="economy-module">
      <div className="fg-meter">
        <div className="fg-ring" style={{ ['--fg-v' as any]: fgValue }}>
          <div className="fg-num">{fgValue}</div>
          <div className="fg-tag">{fgLabel}</div>
        </div>
        <div className="fg-scale">
          <span>FEAR</span>
          <span>NEUTRAL</span>
          <span>GREED</span>
        </div>
      </div>

      <div className="portfolio-block">
        <div className="pb-head">
          <span>PORTFOLIO</span>
          <strong>{typeof total === 'number' ? `$${total.toLocaleString()}` : '—'}</strong>
        </div>
        <div className="pb-rows">
          {(Array.isArray(holdings) ? holdings : []).slice(0, 5).map((h: any, i: number) => (
            <div key={i} className="pb-row">
              <span className="pb-sym">{h.symbol || h.ticker || '???'}</span>
              <span className="pb-amt">{h.amount ?? h.qty ?? '—'}</span>
              <span className="pb-val">
                {h.value ? `$${Number(h.value).toLocaleString()}` : ''}
              </span>
            </div>
          ))}
          {(!Array.isArray(holdings) || holdings.length === 0) && (
            <div className="pb-empty">No active positions</div>
          )}
        </div>
      </div>

      <div className="signal-block">
        <div className="signal-input">
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="Symbol (BTC / ETH / AAPL)"
            onKeyDown={(e) => e.key === 'Enter' && analyse()}
          />
          <button onClick={analyse} disabled={loading}>
            {loading ? 'SCAN…' : 'SCAN'}
          </button>
        </div>
        {signal && (
          <div className="signal-out">
            <span className="so-k">SIGNAL</span>
            <span className="so-v">
              {signal?.signal ?? signal?.action ?? signal?.recommendation ?? '—'}
            </span>
            {signal?.confidence !== undefined && (
              <>
                <span className="so-k">CONF</span>
                <span className="so-v">
                  {Math.round(Number(signal.confidence) * 100)}%
                </span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function classifyFG(v: number): string {
  if (v < 25) return 'EXTREME FEAR';
  if (v < 45) return 'FEAR';
  if (v < 55) return 'NEUTRAL';
  if (v < 75) return 'GREED';
  return 'EXTREME GREED';
}
