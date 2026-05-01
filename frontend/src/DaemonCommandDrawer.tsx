import { useState } from 'react';
import { api, authToken } from './api';

export type DaemonDef = {
  key: string;
  name: string;
  glyph: string;
  role: string;
  accent: string;
};

type Command = {
  id: string;
  label: string;
  detail?: string;
  /** Fires a direct REST call. Used for GET endpoints with no args. */
  call?: (args?: Record<string, string>) => Promise<any>;
  /** When given, shows prompts to collect args before calling the daemon command. */
  prompt?: string[];
  payload?: (args: Record<string, string>) => { command: string; args: any };
};

const COMMANDS: Record<string, Command[]> = {
  blood_ward: [
    { id: 'threats',  label: 'GET THREATS',
      call: () => fetchJson(`${base()}/daemons/blood_ward/threats`) },
    { id: 'block',    label: 'BLOCK IP',  prompt: ['ip'],
      call: async () => null,
      payload: (a) => ({ command: 'block_ip', args: { ip: a.ip } }) },
  ],
  dominion: [
    { id: 'info', label: 'SYSTEM INFO', call: () => fetchJson(`${base()}/daemons/dominion/system_info`) },
  ],
  phantom_recon: [
    { id: 'network', label: 'NETWORK INFO', call: () => fetchJson(`${base()}/daemons/phantom_recon/network_info`) },
    { id: 'scan',    label: 'PORT SCAN', prompt: ['host', 'port'],
      call: async () => null,
      payload: (a) => ({ command: 'scan_port', args: { host: a.host, port: Number(a.port) } }) },
  ],
  crimson_ledger: [
    { id: 'portfolio', label: 'PORTFOLIO', call: () => fetchJson(`${base()}/daemons/crimson_ledger/portfolio`) },
  ],
  storm_caller: [
    { id: 'tasks', label: 'LIST TASKS',  call: () => fetchJson(`${base()}/daemons/storm_caller/tasks`) },
    { id: 'schedule', label: 'SCHEDULE', prompt: ['name', 'cron'],
      call: async () => null,
      payload: (a) => ({ command: 'schedule', args: { name: a.name, cron: a.cron } }) },
  ],
  void_walker: [
    { id: 'tree', label: 'FILE TREE',   call: () => fetchJson(`${base()}/daemons/void_walker/tree`) },
    { id: 'search', label: 'SEARCH', prompt: ['query'],
      call: (args) => fetchJson(`${base()}/daemons/void_walker/search?query=${encodeURIComponent(args?.query || '')}`) },
    { id: 'log',  label: 'OPERATION LOG', call: () => fetchJson(`${base()}/daemons/void_walker/operation_log`) },
  ],
  aether_eye: [
    { id: 'status', label: 'STATUS',  call: () => fetchJson(`${base()}/api/vision/aether-eye/status`) },
    { id: 'ocr',    label: 'OCR SCREEN', call: () => postJson(`${base()}/api/vision/ocr/screen`, {}) },
  ],
  whisper_wind: [
    { id: 'speak', label: 'SPEAK', prompt: ['text'],
      call: async () => null,
      payload: (a) => ({ command: 'speak', args: { text: a.text } }) },
  ],
  iron_crown: [
    { id: 'hw',    label: 'HARDWARE', call: () => fetchJson(`${base()}/daemons/iron_crown/hardware`) },
    { id: 'procs', label: 'PROCESSES', call: () => fetchJson(`${base()}/daemons/iron_crown/processes`) },
  ],
  chronos: [
    { id: 'up',   label: 'UPTIME',    call: () => fetchJson(`${base()}/daemons/chronos/uptime`) },
    { id: 'fc',   label: 'FORECAST',  call: () => fetchJson(`${base()}/daemons/chronos/forecast`) },
    { id: 'snap', label: 'SNAPSHOT',  call: () => postJson(`${base()}/daemons/chronos/snapshot`, {}) },
    { id: 'snaps',label: 'SNAPSHOTS', call: () => fetchJson(`${base()}/daemons/chronos/snapshots`) },
  ],
  data_drake: [
    { id: 'datasets', label: 'DATASETS', call: () => fetchJson(`${base()}/daemons/data_drake/datasets`) },
  ],
};

function base(): string {
  return (import.meta as any).env?.VITE_API_URL || 'http://127.0.0.1:8000';
}

function headers(): HeadersInit {
  const t = authToken.get();
  return {
    'Content-Type': 'application/json',
    ...(t ? { 'X-IGRIS-Token': t, Authorization: `Bearer ${t}` } : {}),
  };
}

async function fetchJson(url: string): Promise<any> {
  const res = await fetch(url, { headers: headers() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
async function postJson(url: string, body: any): Promise<any> {
  const res = await fetch(url, { method: 'POST', headers: headers(), body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

type Props = {
  daemon: DaemonDef | null;
  onClose: () => void;
};

export default function DaemonCommandDrawer({ daemon, onClose }: Props) {
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [args, setArgs] = useState<Record<string, string>>({});

  if (!daemon) return null;
  const cmds = COMMANDS[daemon.key] || [];

  const run = async (cmd: Command) => {
    setRunning(cmd.id);
    setError(null);
    setResult(null);
    try {
      let data: any;
      if (cmd.payload) {
        data = await api.daemonCommand(
          daemon.key,
          cmd.payload(args).command,
          cmd.payload(args).args,
        );
      } else if (cmd.call) {
        data = await cmd.call(args);
      }
      setResult(data);
    } catch (e: any) {
      setError(e?.message || 'Failed');
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="daemon-drawer" role="dialog">
      <div className="daemon-drawer-panel">
        <header className="ddp-head">
          <div className="ddp-title">
            <span className={`ddp-glyph d-${daemon.accent}`}>{daemon.glyph}</span>
            <div>
              <div className="ddp-name">{daemon.name.toUpperCase()}</div>
              <div className="ddp-role">{daemon.role.toUpperCase()}</div>
            </div>
          </div>
          <button className="ddp-close" onClick={onClose}>✕</button>
        </header>

        <div className="ddp-body">
          <div className="ddp-cmd-list">
            {cmds.length === 0 && (
              <div className="ddp-empty">No REST commands mapped for this daemon.</div>
            )}
            {cmds.map((c) => (
              <div key={c.id} className="ddp-cmd">
                <div className="ddp-cmd-row">
                  <button
                    disabled={running !== null}
                    onClick={() => run(c)}
                    className="ddp-cmd-btn"
                  >
                    {running === c.id ? 'RUNNING…' : c.label}
                  </button>
                  {c.detail && <span className="ddp-cmd-detail">{c.detail}</span>}
                </div>
                {c.prompt && c.prompt.length > 0 && (
                  <div className="ddp-cmd-args">
                    {c.prompt.map((p) => (
                      <input
                        key={p}
                        placeholder={p.toUpperCase()}
                        value={args[p] || ''}
                        onChange={(e) => setArgs((cur) => ({ ...cur, [p]: e.target.value }))}
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="ddp-result">
            <div className="ddp-result-head">
              OUTPUT
              {error && <span className="ddp-err">ERR · {error}</span>}
            </div>
            <pre className="ddp-json">
              {result != null ? JSON.stringify(result, null, 2) : '— standby —'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
