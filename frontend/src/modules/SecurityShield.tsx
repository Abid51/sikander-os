import { useEffect, useState } from 'react';
import HudArcBar from '../hud/HudArcBar';
import { api } from '../api';

type LockdownStats = {
  level?: number;
  active?: boolean;
  reason?: string;
  events?: number;
};

export default function SecurityShield() {
  const [lock, setLock] = useState<LockdownStats>({});
  const [threatCount, setThreatCount] = useState(0);
  const [shadowOps, setShadowOps] = useState(0);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [l, t, s] = await Promise.all([
      api.lockdownStats(),
      api.bloodWardThreats(),
      api.shadowStats(),
    ]);
    setLock({
      level:  l?.level ?? l?.current_level ?? 0,
      active: Boolean(l?.active ?? l?.engaged ?? false),
      reason: l?.reason ?? l?.last_reason ?? '—',
      events: l?.events ?? l?.event_count ?? 0,
    });
    const tArr = t?.threats ?? t?.items ?? [];
    setThreatCount(Array.isArray(tArr) ? tArr.length : Number(t?.count || 0));
    setShadowOps(s?.total_ops ?? s?.operations ?? 0);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 9000);
    return () => clearInterval(t);
  }, []);

  const engage = async (level: number) => {
    setBusy(true);
    await api.lockdownEngage(level, 'Operator initiated');
    await load();
    setBusy(false);
  };

  const disengage = async () => {
    setBusy(true);
    await api.lockdownDisengage('');
    await load();
    setBusy(false);
  };

  const shieldPct = lock.active ? Math.min(100, 30 + (lock.level || 0) * 20) : 18;

  return (
    <div className="security-shield">
      <HudArcBar level={shieldPct} label="SHIELD LEVEL" tone={lock.active ? 'crimson' : 'cyan'} />

      <div className="shield-grid">
        <div className="shield-stat">
          <div className="ss-label">STATUS</div>
          <div className={`ss-val ${lock.active ? 'crit' : 'ok'}`}>
            {lock.active ? 'LOCKDOWN' : 'STANDBY'}
          </div>
        </div>
        <div className="shield-stat">
          <div className="ss-label">LEVEL</div>
          <div className="ss-val">L{lock.level ?? 0}</div>
        </div>
        <div className="shield-stat">
          <div className="ss-label">THREATS</div>
          <div className="ss-val">{threatCount}</div>
        </div>
        <div className="shield-stat">
          <div className="ss-label">SHADOW OPS</div>
          <div className="ss-val">{shadowOps}</div>
        </div>
      </div>

      <div className="shield-actions">
        <button disabled={busy} onClick={() => engage(1)}>L1</button>
        <button disabled={busy} onClick={() => engage(2)}>L2</button>
        <button disabled={busy} onClick={() => engage(3)} className="danger">L3</button>
        <button disabled={busy} onClick={disengage} className="safe">Disengage</button>
      </div>

      {lock.reason && lock.reason !== '—' && (
        <div className="shield-reason">reason: {lock.reason}</div>
      )}
    </div>
  );
}
