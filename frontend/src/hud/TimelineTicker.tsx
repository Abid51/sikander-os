import { useEffect, useState } from 'react';
import { useEventStream, type LiveEvent } from '../useEventStream';

const SEED: LiveEvent[] = [
  { id: 's1', time: '', level: 'info',  source: 'CORE',    text: 'Arc reactor online — stable output' },
  { id: 's2', time: '', level: 'info',  source: 'DAEMON',  text: 'Blood Ward perimeter scan complete' },
  { id: 's3', time: '', level: 'info',  source: 'MEMORY',  text: 'Akashic records synchronized' },
  { id: 's4', time: '', level: 'warn',  source: 'ECONOMY', text: 'Fear & Greed index recalibrating' },
  { id: 's5', time: '', level: 'info',  source: 'VISION',  text: 'Aether Eye standby' },
];

function nowStr(): string {
  return new Date().toLocaleTimeString('en-GB', { hour12: false });
}

export default function TimelineTicker() {
  const { events: wsEvents, connected } = useEventStream(20);
  const [fallback, setFallback] = useState<LiveEvent[]>(
    SEED.map((e) => ({ ...e, time: nowStr() }))
  );

  // When disconnected from /ws/events, synthesize ambient chatter so the UI feels alive
  useEffect(() => {
    if (connected) return;
    const t = setInterval(() => {
      setFallback((cur) => {
        const pool: Array<{ source: string; text: string; level: LiveEvent['level'] }> = [
          { source: 'SYSTEM',   text: 'Telemetry heartbeat acknowledged',    level: 'info' },
          { source: 'ORACLE',   text: 'Market signal window refreshed',       level: 'info' },
          { source: 'CHRONOS',  text: 'Temporal snapshot committed',          level: 'info' },
          { source: 'PHANTOM',  text: 'Network topology map regenerated',     level: 'info' },
          { source: 'PSYCHO',   text: 'User profile drift detected',          level: 'warn' },
          { source: 'DREAM',    text: 'Idle cognition cycle completed',       level: 'info' },
          { source: 'BLOOD',    text: 'Intrusion attempt blocked',            level: 'alert' },
        ];
        const pick = pool[Math.floor(Math.random() * pool.length)];
        return [{ id: Math.random().toString(36).slice(2), time: nowStr(), ...pick }, ...cur].slice(0, 14);
      });
    }, 3500);
    return () => clearInterval(t);
  }, [connected]);

  const list = (connected && wsEvents.length ? wsEvents : fallback);

  return (
    <div className="timeline-ticker">
      <div className="ticker-header">
        <span className={`tk-dot ${connected ? '' : 'tk-dot-sim'}`} />
        LIVE EVENT STREAM
        <span className={`tk-conn ${connected ? 'ok' : 'warn'}`}>
          {connected ? '● WS LINKED' : '◇ SIMULATED'}
        </span>
        <span className="tk-sep" />
      </div>
      <div className="ticker-list">
        {list.map((e) => (
          <div key={e.id} className={`tk-row tk-${e.level}`}>
            <span className="tk-time">{e.time}</span>
            <span className="tk-source">{e.source}</span>
            <span className="tk-text">{e.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
