import { useEffect, useState } from 'react';
import { ProviderIcon } from '../ProviderIcon';
import {
  api,
  type CatalogResponse,
  type CatalogItem,
  type ProviderInfo,
} from '../api';

const categoryLabel: Record<string, string> = {
  local: 'LOCAL · LLAMA',
  cloud: 'CLOUD MODELS',
  api:   'API GATEWAYS',
};

type Props = {
  onToast: (msg: string) => void;
};

/**
 * Compact model command panel: live provider list, grouped selector,
 * key entry, temperature/tokens/stream toggle. Styled to match the HUD.
 */
export default function ModelCommand({ onToast }: Props) {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [activeId, setActiveId] = useState('');
  const [keyDraft, setKeyDraft] = useState<Record<string, string>>({});
  const [temp, setTemp] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [showKeys, setShowKeys] = useState(false);

  const load = async () => {
    const [c, p] = await Promise.all([api.modelCatalog(), api.providers()]);
    if (c) {
      setCatalog(c);
      setActiveId(c.active?.id || '');
    }
    if (p) setProviders(p.providers);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  const grouped: Record<string, CatalogItem[]> = catalog?.by_category ?? {
    local: [],
    cloud: [],
    api: [],
  };
  const active = catalog?.items.find((i) => i.id === activeId) || null;

  const switchModel = async (value: string) => {
    setActiveId(value);
    const [provider, ...rest] = value.split('/');
    const model = rest.join('/');
    if (!provider || !model) return;
    const ok = await api.setActiveModel(provider, model);
    onToast(ok ? `Model online → ${provider}/${model}` : 'Model switch failed');
  };

  const saveKey = async (provider: string) => {
    const k = (keyDraft[provider] || '').trim();
    if (!k) return;
    const ok = await api.setApiKey(provider, k);
    onToast(ok ? `Key registered for ${provider}` : 'Key save failed');
    if (ok) {
      setKeyDraft((d) => ({ ...d, [provider]: '' }));
      load();
    }
  };

  const applySettings = async () => {
    const ok = await api.setSettings(temp, maxTokens);
    onToast(ok ? 'Generation settings applied' : 'Settings save failed');
  };

  return (
    <div className="model-command">
      <div className="mc-active-row">
        {active && <ProviderIcon provider={active.provider} size={26} />}
        <div className="mc-active-meta">
          <div className="mc-active-label">ACTIVE MATRIX</div>
          <div className="mc-active-id">{activeId || 'none'}</div>
        </div>
        <select
          value={activeId}
          onChange={(e) => switchModel(e.target.value)}
          className="mc-select"
        >
          <option value="">SELECT MODEL</option>
          {(['local', 'cloud', 'api'] as const).map((cat) =>
            (grouped[cat] || []).length ? (
              <optgroup key={cat} label={categoryLabel[cat]}>
                {grouped[cat].map((item) => (
                  <option
                    key={item.id}
                    value={item.id}
                    disabled={item.needs_key && !item.api_key_set}
                  >
                    {item.provider}/{item.model}
                    {item.needs_key && !item.api_key_set ? '  ◇ no key' : ''}
                  </option>
                ))}
              </optgroup>
            ) : null
          )}
        </select>
      </div>

      <div className="mc-settings">
        <label>
          <span>TEMP</span>
          <input type="range" min={0} max={2} step={0.05}
                 value={temp} onChange={(e) => setTemp(Number(e.target.value))} />
          <b>{temp.toFixed(2)}</b>
        </label>
        <label>
          <span>TOKENS</span>
          <input type="number" min={64} max={32768} step={64}
                 value={maxTokens} onChange={(e) => setMaxTokens(Number(e.target.value))} />
        </label>
        <button onClick={applySettings}>APPLY</button>
        <button onClick={() => setShowKeys((v) => !v)} className="ghost">
          {showKeys ? 'HIDE KEYS' : 'KEYS'}
        </button>
      </div>

      {showKeys && (
        <div className="mc-keys">
          {providers.filter((p) => p.needs_key).map((p) => (
            <div key={p.id} className="mc-key-row">
              <ProviderIcon provider={p.id} size={18} />
              <strong>{p.label}</strong>
              <span className={`mc-tag ${p.api_key_set ? 'ok' : 'warn'}`}>
                {p.api_key_set ? '✓ SET' : '◇ NONE'}
              </span>
              <input
                type="password"
                placeholder={p.api_key_set ? '••••••' : 'API key'}
                value={keyDraft[p.id] || ''}
                onChange={(e) => setKeyDraft((d) => ({ ...d, [p.id]: e.target.value }))}
              />
              <button onClick={() => saveKey(p.id)}>SAVE</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
