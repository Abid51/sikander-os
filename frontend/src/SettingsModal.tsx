import { useEffect, useState } from 'react';
import {
  api,
  type CatalogResponse,
  type ProviderInfo,
} from './api';
import { ProviderIcon } from './ProviderIcon';

type Props = {
  open: boolean;
  onClose: () => void;
  onActive: (id: string) => void;
};

export default function SettingsModal({ open, onClose, onActive }: Props) {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keyDraft, setKeyDraft] = useState<Record<string, string>>({});
  const [temp, setTemp] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [draftModel, setDraftModel] = useState<Record<string, string>>({});

  const buildProvidersFromCatalog = (c: CatalogResponse): ProviderInfo[] => {
    const map = new Map<string, ProviderInfo>();
    for (const item of c.items || []) {
      if (!map.has(item.provider)) {
        map.set(item.provider, {
          id: item.provider,
          label: item.label || item.provider,
          category: item.category,
          needs_key: !!item.needs_key,
          api_key_set: !!item.api_key_set,
          model_count: 0,
          models: [],
        });
      }
      const p = map.get(item.provider)!;
      if (!p.models.includes(item.model)) p.models.push(item.model);
      p.model_count = p.models.length;
      p.api_key_set = p.api_key_set || !!item.api_key_set;
    }
    return Array.from(map.values());
  };

  const refresh = async () => {
    setLoading(true);
    setLoadError('');
    try {
      const [c, p] = await Promise.all([api.modelCatalog(), api.providers()]);
      if (c) setCatalog(c);
      if (p?.providers?.length) setProviders(p.providers);
      else if (c?.items?.length) setProviders(buildProvidersFromCatalog(c));
      else setProviders([]);
      if (!c && !p) setLoadError('Could not fetch model configuration.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    refresh();
  }, [open]);

  if (!open) return null;

  const saveKey = async (provider: string) => {
    const k = (keyDraft[provider] || '').trim();
    if (!k) return;
    const ok = await api.setApiKey(provider, k);
    if (ok) {
      setKeyDraft((d) => ({ ...d, [provider]: '' }));
      await refresh();
    }
  };

  const applySettings = async () => {
    await api.setSettings(temp, maxTokens);
  };

  const activate = async (provider: string, model: string) => {
    const ok = await api.setActiveModel(provider, model);
    if (ok) onActive(`${provider}/${model}`);
  };

  const addModelToProvider = async (provider: string) => {
    const model = (draftModel[provider] || '').trim();
    if (!model) return;
    const ok = await api.registerModel(provider, model);
    if (ok) {
      setDraftModel((d) => ({ ...d, [provider]: '' }));
      await refresh();
    }
  };

  const syncOllamaModels = async () => {
    const models = await api.ollamaList();
    if (!models.length) return;
    for (const m of models) {
      await api.registerModel('ollama', m);
    }
    await refresh();
  };

  const providersByCategory = (category: 'local' | 'cloud' | 'api') =>
    providers.filter((p) => p.category === category);

  const renderProviderCard = (p: ProviderInfo) => {
    const items = (catalog?.items.filter((i) => i.provider === p.id) || []).sort((a, b) =>
      a.model.localeCompare(b.model)
    );
    return (
      <div key={p.id} className={`prov-item ${!p.api_key_set && p.needs_key ? 'dim' : ''}`}>
        <div className="prov-head">
          <ProviderIcon provider={p.id} size={22} />
          <strong>{p.label}</strong>
          <span className={`prov-tag ${p.category}`}>{p.category}</span>
          {p.needs_key && (
            <span className={`prov-key ${p.api_key_set ? 'ok' : 'warn'}`}>
              {p.api_key_set ? 'key set' : 'needs key'}
            </span>
          )}
          <span className="prov-count">{items.length} models</span>
        </div>

        {p.needs_key && (
          <div className="prov-key-row">
            <input
              type="password"
              placeholder={`${p.id} API key`}
              value={keyDraft[p.id] || ''}
              onChange={(e) => setKeyDraft((d) => ({ ...d, [p.id]: e.target.value }))}
            />
            <button onClick={() => saveKey(p.id)} className="btn-sm">Save key</button>
          </div>
        )}

        <div className="prov-add-model">
          <input
            placeholder={`Add ${p.id} model`}
            value={draftModel[p.id] || ''}
            onChange={(e) => setDraftModel((d) => ({ ...d, [p.id]: e.target.value }))}
            onKeyDown={(e) => { if (e.key === 'Enter') addModelToProvider(p.id); }}
          />
          <button onClick={() => addModelToProvider(p.id)} className="btn-sm">Add model</button>
        </div>

        <div className="prov-models">
          {items.map((m) => {
            const id = `${m.provider}/${m.model}`;
            const dis = m.needs_key && !m.api_key_set;
            return (
              <button
                key={id}
                className={`prov-model ${catalog?.active?.id === id ? 'active' : ''}`}
                disabled={dis}
                onClick={() => activate(m.provider, m.model)}
                title={dis ? 'API key required' : 'Set active'}
              >
                {m.model}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <h2>Settings</h2>
          <button className="modal-x" onClick={onClose}>✕</button>
        </header>

        <div className="modal-body">
          {/* Generation */}
          <section className="modal-sec">
            <h3>Generation</h3>
            <div className="gen-row">
              <label>
                Temperature
                <input
                  type="range"
                  min={0} max={2} step={0.05}
                  value={temp}
                  onChange={(e) => setTemp(Number(e.target.value))}
                />
                <b>{temp.toFixed(2)}</b>
              </label>
              <label>
                Max tokens
                <input
                  type="number"
                  min={64} max={32768} step={64}
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                />
              </label>
              <button onClick={applySettings} className="btn-sm primary">Apply</button>
            </div>
          </section>

          {/* Providers + Keys + Models */}
          <section className="modal-sec">
            <h3>Providers & Models</h3>
            <div className="prov-toolbar">
              <button className="btn-sm" onClick={refresh}>Refresh</button>
              <button className="btn-sm" onClick={syncOllamaModels}>Sync local Ollama</button>
            </div>
            <div className="prov-list">
              {loading && <div className="prov-empty">Loading providers...</div>}
              {!loading && loadError && <div className="prov-empty">{loadError}</div>}
              {!loading && !loadError && providers.length === 0 && (
                <div className="prov-empty">
                  No providers found. <button className="btn-sm" onClick={refresh}>Refresh</button>
                </div>
              )}
              {!loading && providersByCategory('local').length > 0 && (
                <>
                  <div className="prov-section-label">Local Models</div>
                  {providersByCategory('local').map(renderProviderCard)}
                </>
              )}
              {!loading && providersByCategory('cloud').length > 0 && (
                <>
                  <div className="prov-section-label">Cloud Models</div>
                  {providersByCategory('cloud').map(renderProviderCard)}
                </>
              )}
              {!loading && providersByCategory('api').length > 0 && (
                <>
                  <div className="prov-section-label">API Models</div>
                  {providersByCategory('api').map(renderProviderCard)}
                </>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
