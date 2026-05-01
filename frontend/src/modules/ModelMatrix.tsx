import { useEffect, useState } from 'react';
import { ProviderIcon } from '../ProviderIcon';
import {
  api,
  type CatalogResponse,
  type CatalogItem,
  type ProviderInfo,
} from '../api';

type Filter = 'all' | 'local' | 'cloud' | 'api';

/**
 * Full-page model integration matrix.
 * Shows every provider card + its models as a dense grid,
 * like the reference dashboard: data-dense, amber key values,
 * yellow-on-black operator aesthetic.
 */
export default function ModelMatrix({
  onToast,
}: {
  onToast: (msg: string) => void;
}) {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [active, setActive] = useState<string>('');
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [keyDraft, setKeyDraft] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = async () => {
    const [c, p] = await Promise.all([api.modelCatalog(), api.providers()]);
    if (c) { setCatalog(c); setActive(c.active?.id || ''); }
    if (p) setProviders(p.providers);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  const switchModel = async (provider: string, model: string) => {
    const id = `${provider}/${model}`;
    setActive(id);
    const ok = await api.setActiveModel(provider, model);
    onToast(ok ? `▶ ACTIVE · ${id}` : `✕ SWITCH FAILED`);
  };

  const saveKey = async (provider: string) => {
    const k = (keyDraft[provider] || '').trim();
    if (!k) return;
    const ok = await api.setApiKey(provider, k);
    onToast(ok ? `✓ KEY STORED · ${provider}` : `✕ KEY FAILED`);
    if (ok) {
      setKeyDraft((d) => ({ ...d, [provider]: '' }));
      load();
    }
  };

  const filteredProviders = providers.filter((p) => {
    if (filter !== 'all' && p.category !== filter) return false;
    if (search && !p.label.toLowerCase().includes(search.toLowerCase())
      && !p.id.toLowerCase().includes(search.toLowerCase())
      && !p.models.some((m) => m.toLowerCase().includes(search.toLowerCase())))
      return false;
    return true;
  });

  const stats = {
    providers: providers.length,
    active:    providers.filter((p) => p.api_key_set || !p.needs_key).length,
    total:     catalog?.total ?? 0,
    local:     (catalog?.by_category.local || []).length,
    cloud:     (catalog?.by_category.cloud || []).length,
    api:       (catalog?.by_category.api || []).length,
  };

  const modelsFor = (p: ProviderInfo): CatalogItem[] => {
    const items = catalog?.items.filter((i) => i.provider === p.id) || [];
    if (!search) return items;
    return items.filter((i) => i.model.toLowerCase().includes(search.toLowerCase()));
  };

  return (
    <div className="model-matrix">
      <div className="mm-head">
        <div className="mm-title">
          <span className="mm-t-main">MODEL INTEGRATION MATRIX</span>
          <span className="mm-t-sub">
            {stats.providers} providers · {stats.active} authenticated · {stats.total} models
          </span>
        </div>
        <div className="mm-filters">
          <input
            className="mm-search"
            placeholder="SEARCH PROVIDER OR MODEL…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {(['all','local','cloud','api'] as Filter[]).map((f) => (
            <button
              key={f}
              className={`mm-filter ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f === 'all' ? 'ALL' : f.toUpperCase()}
              <b>
                {f === 'all' ? stats.total :
                 f === 'local' ? stats.local :
                 f === 'cloud' ? stats.cloud : stats.api}
              </b>
            </button>
          ))}
        </div>
      </div>

      <div className="mm-stats">
        <Stat label="ACTIVE"      value={active || 'NONE'} tone="yellow" mono big />
        <Stat label="LOCAL"       value={String(stats.local)} />
        <Stat label="CLOUD"       value={String(stats.cloud)} />
        <Stat label="API"         value={String(stats.api)} />
        <Stat label="AUTH"        value={`${stats.active}/${stats.providers}`} tone="green" />
      </div>

      <div className="mm-grid">
        {filteredProviders.map((p) => {
          const items = modelsFor(p);
          const isExp = expanded === p.id;
          const displayItems = isExp ? items : items.slice(0, 4);
          const isActive = active.startsWith(`${p.id}/`);

          return (
            <div key={p.id} className={`mm-provider ${isActive ? 'active' : ''} ${!p.api_key_set && p.needs_key ? 'needs-key' : ''}`}>
              <div className="mm-p-head">
                <ProviderIcon provider={p.id} size={26} />
                <div className="mm-p-meta">
                  <div className="mm-p-name">{p.label}</div>
                  <div className="mm-p-sub">
                    <span className={`mm-cat mm-cat-${p.category}`}>{p.category.toUpperCase()}</span>
                    <span>{p.model_count} MODELS</span>
                    {p.needs_key && (
                      <span className={`mm-keystate ${p.api_key_set ? 'ok' : 'warn'}`}>
                        {p.api_key_set ? 'KEY ✓' : 'NO KEY'}
                      </span>
                    )}
                  </div>
                </div>
                {p.site && (
                  <a className="mm-p-link" href={p.site} target="_blank" rel="noreferrer">
                    ↗
                  </a>
                )}
              </div>

              {p.needs_key && !p.api_key_set && (
                <div className="mm-p-keyrow">
                  <input
                    type="password"
                    placeholder={`${p.id} API key`}
                    value={keyDraft[p.id] || ''}
                    onChange={(e) => setKeyDraft((d) => ({ ...d, [p.id]: e.target.value }))}
                  />
                  <button onClick={() => saveKey(p.id)}>STORE</button>
                </div>
              )}

              <div className="mm-p-models">
                {displayItems.map((m) => {
                  const id = `${m.provider}/${m.model}`;
                  const on = active === id;
                  const disabled = m.needs_key && !m.api_key_set;
                  return (
                    <button
                      key={id}
                      className={`mm-model ${on ? 'on' : ''} ${disabled ? 'dis' : ''}`}
                      disabled={disabled}
                      onClick={() => switchModel(m.provider, m.model)}
                      title={disabled ? 'API key required' : id}
                    >
                      {on && <span className="mm-mdot" />}
                      <span className="mm-mname">{m.model}</span>
                    </button>
                  );
                })}
                {items.length > 4 && !isExp && (
                  <button
                    className="mm-expand"
                    onClick={() => setExpanded(p.id)}
                  >
                    +{items.length - 4} MORE
                  </button>
                )}
                {isExp && (
                  <button
                    className="mm-expand"
                    onClick={() => setExpanded(null)}
                  >
                    COLLAPSE
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({
  label, value, tone = 'gray', mono, big,
}: {
  label: string;
  value: string;
  tone?: 'gray' | 'yellow' | 'green';
  mono?: boolean;
  big?: boolean;
}) {
  return (
    <div className={`mm-stat mm-stat-${tone} ${big ? 'big' : ''}`}>
      <span className="mm-stat-l">{label}</span>
      <span className={`mm-stat-v ${mono ? 'mono' : ''}`}>{value}</span>
    </div>
  );
}
