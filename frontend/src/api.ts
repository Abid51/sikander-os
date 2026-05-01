/**
 * Centralised API client for the Sikander OS frontend.
 * Base URL is overridable via VITE_API_URL (useful in Docker / prod).
 */

export const API_BASE: string =
  (import.meta as any).env?.VITE_API_URL || 'http://127.0.0.1:8000';

const TOKEN_KEY = 'igris.auth.token.v1';

// ──────────────────────────────────────────────────────────────────
// Token management (localStorage)
// ──────────────────────────────────────────────────────────────────

export const authToken = {
  get(): string {
    try {
      return localStorage.getItem(TOKEN_KEY) || '';
    } catch {
      return '';
    }
  },
  set(token: string): void {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

function authHeaders(): HeadersInit {
  const t = authToken.get();
  return t ? { 'X-IGRIS-Token': t, Authorization: `Bearer ${t}` } : {};
}

/** Listener called whenever a 401 is seen — used by the login gate. */
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;
export function setUnauthorizedHandler(h: UnauthorizedHandler | null) {
  onUnauthorized = h;
}

async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(input, {
    ...init,
    headers: {
      ...(init.headers || {}),
      ...authHeaders(),
    },
  });
  if (res.status === 401 && onUnauthorized) {
    onUnauthorized();
  }
  return res;
}

// ──────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────

export type ProviderInfo = {
  id: string;
  label: string;
  category: 'local' | 'cloud' | 'api';
  needs_key: boolean;
  api_key_set: boolean;
  site?: string;
  model_count: number;
  models: string[];
};

export type CatalogItem = {
  id: string;
  provider: string;
  model: string;
  category: 'local' | 'cloud' | 'api';
  label: string;
  needs_key: boolean;
  api_key_set: boolean;
};

export type CatalogResponse = {
  total: number;
  by_category: Record<'local' | 'cloud' | 'api', CatalogItem[]>;
  items: CatalogItem[];
  active: { provider: string; model: string; id: string };
};

export type HealthResponse = {
  status: 'online' | 'offline' | 'no_key' | 'litellm_missing' | 'error';
  provider: string;
  model: string;
  latency_ms: number;
  available_models?: string[];
  litellm_enabled?: boolean;
  error?: string;
};

export type AuthStatus = {
  auth_enabled: boolean;
  mode?: string;
  exempt_paths?: string[];
};

export type PendingActionResponse = {
  has_pending_action: boolean;
  pending_action?: { tool_name: string; tool_args: Record<string, any> } | null;
  request_id?: string;
};

// ──────────────────────────────────────────────────────────────────
// API helpers
// ──────────────────────────────────────────────────────────────────

async function safeJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async authStatus(): Promise<AuthStatus | null> {
    try {
      return await safeJson<AuthStatus>(await fetch(`${API_BASE}/auth/status`));
    } catch {
      return null;
    }
  },

  /** Returns true if provided token is valid (or if auth disabled). */
  async verifyToken(token: string): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/auth/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-IGRIS-Token': token, Authorization: `Bearer ${token}` } : {}),
        },
        body: '{}',
      });
      return res.ok;
    } catch {
      return false;
    }
  },

  async health(): Promise<{ status: string } | null> {
    try {
      const res = await authedFetch(`${API_BASE}/health`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async modelCatalog(): Promise<CatalogResponse | null> {
    try {
      return await safeJson<CatalogResponse>(
        await authedFetch(`${API_BASE}/models/catalog`)
      );
    } catch {
      return null;
    }
  },

  async providers(): Promise<{ providers: ProviderInfo[]; litellm_enabled: boolean } | null> {
    try {
      return await safeJson(await authedFetch(`${API_BASE}/models/providers`));
    } catch {
      return null;
    }
  },

  async modelHealth(): Promise<HealthResponse | null> {
    try {
      return await safeJson<HealthResponse>(
        await authedFetch(`${API_BASE}/models/health`)
      );
    } catch {
      return null;
    }
  },

  async setActiveModel(provider: string, model: string): Promise<boolean> {
    try {
      const res = await authedFetch(`${API_BASE}/models/active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model }),
      });
      return res.ok;
    } catch {
      return false;
    }
  },

  async registerModel(provider: string, model: string): Promise<boolean> {
    try {
      const res = await authedFetch(`${API_BASE}/models/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model }),
      });
      return res.ok;
    } catch {
      return false;
    }
  },

  async ollamaList(): Promise<string[]> {
    try {
      const data = await safeJson<{ models: string[] }>(
        await authedFetch(`${API_BASE}/models/ollama/list`)
      );
      return data.models || [];
    } catch {
      return [];
    }
  },

  async ollamaPull(model: string): Promise<boolean> {
    try {
      const res = await authedFetch(`${API_BASE}/models/ollama/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      });
      return res.ok;
    } catch {
      return false;
    }
  },

  async setApiKey(provider: string, apiKey: string): Promise<boolean> {
    try {
      const res = await authedFetch(`${API_BASE}/models/apikey`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      return res.ok;
    } catch {
      return false;
    }
  },

  async setSettings(temperature: number, maxTokens: number): Promise<boolean> {
    try {
      const res = await authedFetch(`${API_BASE}/models/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temperature, max_tokens: maxTokens }),
      });
      return res.ok;
    } catch {
      return false;
    }
  },

  async snapshot(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/observability/snapshot`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── System / monitoring ───────────────────────────────────────────────

  async systemStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/system/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async monitorStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/monitor/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async monitorHealthDetailed(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/monitor/health-detailed`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── Daemons ──────────────────────────────────────────────────────────

  async daemonsStatus(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/daemons/status`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async daemonCommand(name: string, command: string, args: any = {}): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/daemons/${name}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, params: args }),
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── Security / lockdown / shadow ─────────────────────────────────────

  async lockdownStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/lockdown/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async lockdownEngage(level = 2, reason = 'Manual'): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/lockdown/engage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level, reason }),
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async lockdownDisengage(token = ''): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/lockdown/disengage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auth_token: token }),
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async shadowStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/shadow/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async bloodWardThreats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/daemons/blood_ward/threats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── Economy ──────────────────────────────────────────────────────────

  async economyStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/economy/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async fearGreed(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/economy/fear-greed`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async portfolio(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/economy/portfolio`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async economySignal(symbol: string): Promise<any | null> {
    try {
      const res = await authedFetch(
        `${API_BASE}/economy/signal/${encodeURIComponent(symbol)}`
      );
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── Memory / Akashic / Graph ─────────────────────────────────────────

  async memoryStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/memory/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async akashicStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/akashic/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async akashicRecent(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/akashic/recent`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async graphStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/graph/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── Emotion / Dream / Persona / Predict ──────────────────────────────

  async emotionCurrent(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/emotion/current`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async personaStats(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/persona/stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async personaModes(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/persona/modes`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async personaSwitch(mode: string): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/persona/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async dreamReport(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/dream/report`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async predictNow(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/predict/now`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── Quantum thinking ─────────────────────────────────────────────────

  async quantumAngles(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/quantum/angles`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async quantumQuickThink(prompt: string, angle?: string): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/quantum/quick-think`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: prompt, angle_id: angle || 'first_principles' }),
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── Vision ───────────────────────────────────────────────────────────

  async aetherStatus(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/api/vision/aether-eye/status`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async captureScreen(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/api/vision/screen/capture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async ocrScreen(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/api/vision/ocr/screen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── IGRIS supremacy / god-mode / omega ───────────────────────────────

  async supremacy(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/igris/supremacy`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async godMode(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/igris/god-mode`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async omega(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/igris/omega`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── Tools ─────────────────────────────────────────────────────────────

  async toolsList(): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/tools/list`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async webSearch(query: string): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/tools/web/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async calculate(expression: string): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/tools/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression }),
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async codeRun(code: string, language = 'python'): Promise<any | null> {
    try {
      const res = await authedFetch(`${API_BASE}/tools/code/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, language }),
      });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  // ─── WebSocket helpers ────────────────────────────────────────────────

  wsUrl(path: string): string {
    const base = API_BASE.replace(/^http/, 'ws');
    return `${base}${path}`;
  },

  async chat(message: string): Promise<string> {
    const res = await authedFetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const data = await res.json().catch(() => ({}));
    return String(data?.response ?? data?.text ?? data?.error ?? 'No response');
  },

  /**
   * Stream chat via SSE from `/chat/stream`.
   * Calls `onChunk` for each incremental piece, returns full text.
   */
  async chatStream(
    message: string,
    onChunk: (chunk: string) => void,
    signal?: AbortSignal
  ): Promise<string> {
    const res = await authedFetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
      signal,
    });
    if (!res.ok || !res.body) {
      throw new Error(`Stream failed: HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let full = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data:')) continue;
        const payload = trimmed.slice(5).trim();
        if (!payload || payload === '[DONE]') continue;
        try {
          const obj = JSON.parse(payload);
          if (obj.chunk) {
            full += obj.chunk;
            onChunk(obj.chunk);
          }
          if (obj.done && obj.text) {
            full = obj.text;
          }
          if (obj.error) {
            throw new Error(obj.error);
          }
        } catch (err) {
          if (err instanceof SyntaxError) {
            continue;
          }
          throw err;
        }
      }
    }

    return full;
  },

  async getPendingAction(): Promise<PendingActionResponse | null> {
    try {
      return await safeJson<PendingActionResponse>(await authedFetch(`${API_BASE}/actions/pending`));
    } catch {
      return null;
    }
  },

  async approvePendingAction(): Promise<{ ok: boolean; result?: any; error?: string } | null> {
    try {
      return await safeJson(await authedFetch(`${API_BASE}/actions/pending/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      }));
    } catch {
      return null;
    }
  },

  async cancelPendingAction(reason = 'cancelled_from_ui'): Promise<{ ok: boolean } | null> {
    try {
      return await safeJson(await authedFetch(`${API_BASE}/actions/pending/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      }));
    } catch {
      return null;
    }
  },

  /**
   * Self-learning: thumbs feedback wired to backend neural memory (via feedback_engine).
   * POST `/igris/feedback/submit`
   */
  async submitFeedback(params: {
    user_message: string;
    igris_response: string;
    rating: -1 | 0 | 1;
    message_id?: string;
    feedback_text?: string;
    model_used?: string;
  }): Promise<{ success?: boolean; feedback_id?: string } | null> {
    try {
      return await safeJson(
        await authedFetch(`${API_BASE}/igris/feedback/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        })
      );
    } catch {
      return null;
    }
  },
};
