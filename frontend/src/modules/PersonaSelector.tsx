import { useEffect, useState } from 'react';
import { api } from '../api';

export default function PersonaSelector() {
  const [modes, setModes] = useState<any[]>([]);
  const [active, setActive] = useState<string>('');
  const [emotion, setEmotion] = useState<any>({});

  const load = async () => {
    const [m, s, e] = await Promise.all([
      api.personaModes(),
      api.personaStats(),
      api.emotionCurrent(),
    ]);
    const list = m?.modes ?? m?.personas ?? (Array.isArray(m) ? m : []);
    setModes(Array.isArray(list) ? list : []);
    setActive(s?.active_mode ?? s?.current ?? s?.mode ?? '');
    setEmotion(e || {});
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const pick = async (mode: string) => {
    setActive(mode);
    await api.personaSwitch(mode);
  };

  const modeList = modes.length
    ? modes
    : [
        { id: 'commander', label: 'Commander' },
        { id: 'scholar',   label: 'Scholar'   },
        { id: 'warrior',   label: 'Warrior'   },
        { id: 'oracle',    label: 'Oracle'    },
      ];

  const emotionLabel = emotion?.emotion || emotion?.current || emotion?.label || 'calm';
  const emotionIntensity = Number(emotion?.intensity ?? emotion?.level ?? 0.5);

  return (
    <div className="persona-selector">
      <div className="ps-emotion">
        <div className="pe-label">EMOTION</div>
        <div className="pe-val">{String(emotionLabel).toUpperCase()}</div>
        <div className="pe-bar" style={{ ['--pe-v' as any]: `${Math.round(emotionIntensity * 100)}%` }} />
      </div>
      <div className="ps-list">
        {modeList.map((m: any) => {
          const id = m.id || m.name || m.mode || m.label;
          return (
            <button
              key={id}
              className={`ps-pill ${active === id ? 'active' : ''}`}
              onClick={() => pick(id)}
            >
              {String(m.label || m.name || id).toUpperCase()}
            </button>
          );
        })}
      </div>
    </div>
  );
}
