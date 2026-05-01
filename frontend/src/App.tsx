import './index.css';
import './app.css';
import { useEffect, useRef, useState } from 'react';
import { api, authToken, setUnauthorizedHandler } from './api';
import LoginGate from './LoginGate';
import ChatMessage from './ChatMessage';
import SettingsModal from './SettingsModal';
import LaunchModal from './LaunchModal';
import VoiceOrb from './VoiceOrb';
import { useChats } from './useChats';
import AiWorkspacePanel from './modules/AiWorkspacePanel';

const VOICE_UI_KEY = 'igris.voice.ui.v1';
type VoiceUiMode = 'float' | 'dock';

export default function App() {
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);
  const [authed, setAuthed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [launchOpen, setLaunchOpen] = useState(false);

  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [activeModel, setActiveModel] = useState<string>('');
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const [modelItems, setModelItems] = useState<Array<{ provider: string; model: string; id: string; category: string }>>([]);
  const [localOllamaModels, setLocalOllamaModels] = useState<Set<string>>(new Set());
  const [pullingModel, setPullingModel] = useState<string>('');
  const [newModel, setNewModel] = useState('');
  const [voiceUi, setVoiceUi] = useState<VoiceUiMode>(() => {
    try {
      const v = localStorage.getItem(VOICE_UI_KEY);
      if (v === 'float' || v === 'dock') return v;
    } catch { /* ignore */ }
    return 'float';
  });

  const chats = useChats();
  const boxRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auth boot
  useEffect(() => {
    setUnauthorizedHandler(() => { authToken.clear(); setAuthed(false); });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const s = await api.authStatus();
      if (cancelled) return;
      const enabled = !!s?.auth_enabled;
      setAuthEnabled(enabled);
      if (!enabled) { setAuthed(true); return; }
      const t = authToken.get();
      if (!t) { setAuthed(false); return; }
      const ok = await api.verifyToken(t);
      if (!cancelled) setAuthed(ok);
    })();
    return () => { cancelled = true; };
  }, []);

  // Load active model
  useEffect(() => {
    if (!authed) return;
    (async () => {
      const c = await api.modelCatalog();
      if (c?.active?.id) setActiveModel(c.active.id);
    })();
  }, [authed]);

  useEffect(() => {
    try { localStorage.setItem(VOICE_UI_KEY, voiceUi); } catch { /* ignore */ }
  }, [voiceUi]);

  // Autoscroll
  useEffect(() => {
    const el = boxRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chats.active?.messages.length]);

  useEffect(() => {
    if (!modelMenuOpen) return;
    const onDocClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target?.closest('.comp-model-wrap')) setModelMenuOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [modelMenuOpen]);

  const onActiveModel = (id: string) => setActiveModel(id);

  const refreshModels = async () => {
    const c = await api.modelCatalog();
    if (c?.active?.id) setActiveModel(c.active.id);
    if (c?.items) setModelItems(c.items as any);
  };

  const openModelMenu = async () => {
    await refreshModels();
    const local = await api.ollamaList();
    setLocalOllamaModels(new Set((local || []).map((m) => (m || '').trim())));
    setModelMenuOpen(true);
  };

  const switchModel = async (provider: string, model: string) => {
    const ok = await api.setActiveModel(provider, model);
    if (ok) {
      setActiveModel(`${provider}/${model}`);
      setModelMenuOpen(false);
    }
  };

  const addModel = async () => {
    const raw = newModel.trim();
    if (!raw) return;
    let provider = 'ollama';
    let model = raw;
    if (raw.includes('/')) {
      const [p, ...rest] = raw.split('/');
      provider = p.trim().toLowerCase() || 'ollama';
      model = rest.join('/').trim();
    }
    if (!model) return;
    const ok = await api.registerModel(provider, model);
    if (ok) {
      setNewModel('');
      await refreshModels();
    }
  };

  const pullModel = async (model: string) => {
    if (!model || pullingModel) return;
    setPullingModel(model);
    const ok = await api.ollamaPull(model);
    if (ok) {
      const next = new Set(localOllamaModels);
      next.add(model);
      setLocalOllamaModels(next);
      await refreshModels();
    }
    setPullingModel('');
  };

  const runChatStream = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    let chatId = chats.activeId;
    if (!chatId) chatId = chats.createChat();

    chats.appendMessage(chatId, { role: 'user', text: trimmed, ts: Date.now() });
    setBusy(true);

    chats.appendMessage(chatId, { role: 'assistant', text: '', ts: Date.now() });
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await api.chatStream(
        trimmed,
        (chunk) => chats.updateLastAssistant(chatId!, (cur) => cur + chunk),
        ctrl.signal
      );
    } catch (err: any) {
      chats.updateLastAssistant(chatId, (cur) =>
        cur || `Error: ${err?.message || 'stream failed'}`
      );
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    await runChatStream(text);
  };

  const stop = () => { abortRef.current?.abort(); abortRef.current = null; setBusy(false); };

  // ── render ──────────────────────────────────────────────────

  if (authEnabled === null) {
    return <div className="boot-screen"><div className="boot-orb" /><p>CONNECTING…</p></div>;
  }

  if (authEnabled && !authed) {
    return (
      <div className="app-root">
        <LoginGate onAuthenticated={() => setAuthed(true)} />
      </div>
    );
  }

  const msgs = chats.active?.messages || [];
  const empty = msgs.length === 0;

  return (
    <div className="app-root hud-app">
      <aside className={`sidebar hud-sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
        <div className="sidebar-top">
          <button
            className="icon-btn sidebar-toggle"
            onClick={() => setSidebarOpen((v) => !v)}
            title={sidebarOpen ? 'Collapse' : 'Expand'}
          >
            <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6">
              <rect x="3" y="4" width="14" height="12" rx="1.5" />
              <line x1="8" y1="4" x2="8" y2="16" />
            </svg>
          </button>
        </div>

        {sidebarOpen && (
          <>
            <nav className="nav-block">
              <button className="nav-item active" onClick={() => chats.createChat()}>
                <IconNewChat />
                <span>New Chat</span>
              </button>
              <button className="nav-item" onClick={() => setLaunchOpen(true)}>
                <IconLaunch />
                <span>Launch</span>
              </button>
              <button className="nav-item" onClick={() => setSettingsOpen(true)}>
                <IconSettings />
                <span>Settings</span>
              </button>
            </nav>

            {chats.sessions.length > 0 && (
              <div className="nav-block older">
                <div className="nav-section">Older</div>
                {chats.sessions.map((s) => (
                  <button
                    key={s.id}
                    className={`older-item ${s.id === chats.activeId ? 'active' : ''}`}
                    title={s.title}
                    onClick={() => chats.openChat(s.id)}
                  >
                    <span className="older-title">{s.title || 'New chat'}</span>
                    <span
                      className="older-del"
                      onClick={(e) => { e.stopPropagation(); chats.deleteChat(s.id); }}
                      title="Delete"
                    >×</span>
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </aside>

      <main className="chat-main hud-surface">
        <header className="hud-topbar" role="banner">
          <div className="hud-topbar-inner">
            <div className="hud-brand">
              <span className="hud-brand-icon" aria-hidden>
                ◈
              </span>
              <div className="hud-brand-stack">
                <span className="hud-brand-title">SIKANDER OS</span>
                <span className="hud-brand-tag">IGRIS · OPS CHANNEL · CHAT HUD</span>
              </div>
            </div>
            <div className="hud-topbar-center">
              <div className="hud-voice-switch" role="group" aria-label="Voice HUD mode">
                <button
                  type="button"
                  className={`hud-vsw ${voiceUi === 'float' ? 'active' : ''}`}
                  onClick={() => setVoiceUi('float')}
                  title="Floating voice orb (corner)"
                >
                  ORB
                </button>
                <button
                  type="button"
                  className={`hud-vsw ${voiceUi === 'dock' ? 'active' : ''}`}
                  onClick={() => setVoiceUi('dock')}
                  title="Dock mic HUD next to composer"
                >
                  DOCK
                </button>
              </div>
            </div>
            <div className="hud-meta">
              <span className="hud-link-pill">
                <span className="hud-dot" aria-hidden />
                UPLINK ACTIVE
              </span>
              <span className="hud-meta-muted">STREAM · MARKDOWN · MULTI-MODEL</span>
            </div>
          </div>
        </header>

        <div className="chat-workspace-wrap">
          <div className="chat-primary">
            <div className="chat-scroll" ref={boxRef}>
              {empty ? (
                <div className="welcome hud-welcome">
                  <Llama />
                  <div className="welcome-kicker">OPERATOR CHANNEL</div>
                  <div className="welcome-text">Direct channel open · state your directive</div>
                  <div className="welcome-sub">Roman Urdu + English · streaming · tools-ready</div>
                </div>
              ) : (
                <div className="messages">
                  {msgs.map((m, i) => (
                    <ChatMessage key={`${m.role}-${i}`} role={m.role} text={m.text} />
                  ))}
                </div>
              )}
            </div>

            <div className="composer-wrap hud-composer-wrap">
              <div className="composer hud-composer">
            <textarea
              placeholder="Send a message"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={1}
            />
            <div className="composer-row">
              <button className="comp-btn" title="Attach" onClick={() => setLaunchOpen(true)}>
                <span>+</span>
              </button>
              <button className="comp-btn" title="Web / tools" onClick={() => setLaunchOpen(true)}>
                <IconGlobe />
              </button>
              {voiceUi === 'dock' ? (
                <VoiceOrb variant="inline" onVoiceSubmit={runChatStream} disabled={busy} />
              ) : null}

              <div className="comp-model-wrap">
              <div className="comp-model" onClick={openModelMenu} title="Change model">
                <span>{activeModel || 'select model'}</span>
                <svg viewBox="0 0 10 6" width="10" height="6">
                  <path d="M1 1 L5 5 L9 1" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </div>
              {modelMenuOpen && (
                <div className="model-menu">
                  <div className="model-menu-head">Models</div>
                  <div className="model-menu-list">
                    {modelItems.slice(0, 80).map((m) => (
                      <div key={m.id} className={`model-menu-item ${activeModel === m.id ? 'active' : ''}`}>
                        <button
                          className="model-menu-select"
                          onClick={() => switchModel(m.provider, m.model)}
                        >
                          <span>{m.model}</span>
                          <small>{m.provider}</small>
                        </button>
                        {m.provider === 'ollama' && !localOllamaModels.has(m.model) && (
                          <button
                            className="model-menu-download"
                            title={`Download ${m.model}`}
                            disabled={pullingModel === m.model}
                            onClick={() => pullModel(m.model)}
                          >
                            {pullingModel === m.model ? '...' : '⬇'}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="model-menu-add">
                    <input
                      placeholder="Add model (e.g. ollama/qwen3:latest)"
                      value={newModel}
                      onChange={(e) => setNewModel(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') addModel(); }}
                    />
                    <button onClick={addModel}>Add</button>
                  </div>
                  <button className="model-menu-manage" onClick={() => { setModelMenuOpen(false); setSettingsOpen(true); }}>
                    Manage providers and API keys
                  </button>
                </div>
              )}
              </div>

              <div className="comp-spacer" />

              {busy ? (
                <button className="comp-send stop" onClick={stop} title="Stop">
                  <svg viewBox="0 0 12 12" width="10" height="10">
                    <rect x="2" y="2" width="8" height="8" fill="currentColor" />
                  </svg>
                </button>
              ) : (
                <button
                  className="comp-send"
                  onClick={send}
                  disabled={!input.trim()}
                  title="Send"
                >
                  <svg viewBox="0 0 14 14" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M2 7 L12 7 M7 2 L12 7 L7 12" />
                  </svg>
                </button>
              )}
              </div>
            </div>
          </div>
          </div>
          <AiWorkspacePanel busy={busy} activeModel={activeModel} messages={msgs} />
        </div>
      </main>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onActive={onActiveModel}
      />
      <LaunchModal
        open={launchOpen}
        onClose={() => setLaunchOpen(false)}
      />

      {voiceUi === 'float' ? (
        <VoiceOrb variant="float" onVoiceSubmit={runChatStream} disabled={busy} />
      ) : null}
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────

function IconNewChat() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M4 15 L4 5 Q4 4 5 4 L13 4 Q14 4 14 5 L14 11 Q14 12 13 12 L8 12 L4 15" strokeLinejoin="round" />
      <line x1="17" y1="14" x2="17" y2="18" /><line x1="15" y1="16" x2="19" y2="16" />
    </svg>
  );
}
function IconLaunch() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M4 16 Q4 9 10 4 Q16 9 16 16 Z" strokeLinejoin="round" />
      <circle cx="10" cy="9" r="1.6" />
      <path d="M6 15 L4 18 M14 15 L16 18" strokeLinecap="round" />
    </svg>
  );
}
function IconSettings() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="10" cy="10" r="2.4" />
      <path d="M10 2 L10 4 M10 16 L10 18 M2 10 L4 10 M16 10 L18 10 M4.3 4.3 L5.8 5.8 M14.2 14.2 L15.7 15.7 M4.3 15.7 L5.8 14.2 M14.2 5.8 L15.7 4.3" strokeLinecap="round" />
    </svg>
  );
}
function IconGlobe() {
  return (
    <svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <circle cx="9" cy="9" r="7" />
      <line x1="2" y1="9" x2="16" y2="9" />
      <path d="M9 2 Q13 9 9 16 Q5 9 9 2" />
    </svg>
  );
}
function Llama() {
  return (
    <div className="llama">
      <svg viewBox="0 0 64 64" width="64" height="64" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 20 Q22 13 30 13 Q38 13 38 20 L42 22 Q46 24 46 28 L46 44 Q46 50 40 50 L24 50 Q18 50 18 44 L18 30 Q18 24 22 22 Z" />
        <path d="M22 20 L18 14 M38 20 L42 14" />
        <circle cx="26" cy="30" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="34" cy="30" r="1.5" fill="currentColor" stroke="none" />
        <path d="M27 36 Q30 38 33 36" />
      </svg>
    </div>
  );
}
