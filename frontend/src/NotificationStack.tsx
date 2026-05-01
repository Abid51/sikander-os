import { useEffect, useRef, useState } from 'react';

export type Notif = {
  id: string;
  title: string;
  body?: string;
  level?: 'info' | 'warn' | 'ok' | 'alert';
  ts: number;
};

type Props = {
  bucket: Notif[];
  onDismiss: (id: string) => void;
};

export default function NotificationStack({ bucket, onDismiss }: Props) {
  return (
    <div className="notif-stack">
      {bucket.slice(-5).map((n) => (
        <NotifCard key={n.id} n={n} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function NotifCard({ n, onDismiss }: { n: Notif; onDismiss: (id: string) => void }) {
  const [prog, setProg] = useState(100);
  const start = useRef(Date.now());
  useEffect(() => {
    const dur = 6000;
    const t = setInterval(() => {
      const elapsed = Date.now() - start.current;
      const left = Math.max(0, 100 - (elapsed / dur) * 100);
      setProg(left);
      if (elapsed >= dur) { clearInterval(t); onDismiss(n.id); }
    }, 80);
    return () => clearInterval(t);
  }, [n.id, onDismiss]);

  return (
    <div className={`notif-card nc-${n.level || 'info'}`}>
      <div className="nc-head">
        <span className="nc-tag">{(n.level || 'info').toUpperCase()}</span>
        <span className="nc-title">{n.title}</span>
        <button onClick={() => onDismiss(n.id)} className="nc-x">✕</button>
      </div>
      {n.body && <div className="nc-body">{n.body}</div>}
      <div className="nc-progress"><span style={{ width: `${prog}%` }} /></div>
    </div>
  );
}

/** Hook + dispatcher for ambient notifications. */
export function useNotifier() {
  const [bucket, setBucket] = useState<Notif[]>([]);
  const push = (n: Omit<Notif, 'id' | 'ts'>) => {
    setBucket((cur) => [
      ...cur,
      { ...n, id: Math.random().toString(36).slice(2), ts: Date.now() },
    ].slice(-20));
  };
  const dismiss = (id: string) => setBucket((cur) => cur.filter((x) => x.id !== id));
  return { bucket, push, dismiss };
}
