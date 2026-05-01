import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';

type ChatMsg = { role: 'user' | 'assistant'; text: string };

type Props = {
  busy: boolean;
  activeModel: string;
  messages: ChatMsg[];
};

export default function AiWorkspacePanel({ busy, activeModel, messages }: Props) {
  const [toolsCount, setToolsCount] = useState(0);
  const [aether, setAether] = useState<any>(null);
  const [pending, setPending] = useState<any>(null);
  const [lastSync, setLastSync] = useState<number>(0);

  useEffect(() => {
    let alive = true;
    const sync = async () => {
      const [tools, aetherStatus, pendingAction] = await Promise.all([
        api.toolsList(),
        api.aetherStatus(),
        api.getPendingAction(),
      ]);
      if (!alive) return;
      setToolsCount(Array.isArray(tools?.tools) ? tools.tools.length : 0);
      setAether(aetherStatus || null);
      setPending(pendingAction?.pending_action || null);
      setLastSync(Date.now());
    };
    sync();
    const t = window.setInterval(sync, 5000);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, []);

  const lastUser = useMemo(
    () => [...messages].reverse().find((m) => m.role === 'user')?.text || '',
    [messages]
  );
  const lastAssistant = useMemo(
    () => [...messages].reverse().find((m) => m.role === 'assistant')?.text || '',
    [messages]
  );

  return (
    <aside className="ai-workspace" aria-label="AI Workspace">
      <div className="aiw-head">AI WORKSPACE</div>
      <div className="aiw-grid">
        <Stat label="ENGINE" value={busy ? 'WORKING' : 'IDLE'} ok={!busy} />
        <Stat
          label="AETHER EYE"
          value={aether?.status ? String(aether.status).toUpperCase() : 'OFFLINE'}
          ok={aether?.is_running === true}
        />
        <Stat label="TOOLS" value={String(toolsCount)} ok={toolsCount > 0} />
        <Stat label="MODEL" value={activeModel || 'N/A'} ok={!!activeModel} />
      </div>

      <div className="aiw-block">
        <div className="aiw-label">LAST USER COMMAND</div>
        <div className="aiw-text">{lastUser || 'No command yet.'}</div>
      </div>

      <div className="aiw-block">
        <div className="aiw-label">LATEST AI OUTPUT</div>
        <div className="aiw-text">{lastAssistant ? lastAssistant.slice(0, 240) : 'No response yet.'}</div>
      </div>

      <div className="aiw-block">
        <div className="aiw-label">PENDING ACTION</div>
        <div className="aiw-text">
          {pending ? `${pending.tool_name} ${JSON.stringify(pending.tool_args || {})}` : 'None'}
        </div>
      </div>

      <div className="aiw-foot">
        {lastSync ? `Synced ${new Date(lastSync).toLocaleTimeString()}` : 'Syncing...'}
      </div>
    </aside>
  );
}

function Stat({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="aiw-stat">
      <span>{label}</span>
      <b className={ok ? 'ok' : 'warn'}>{value}</b>
    </div>
  );
}

