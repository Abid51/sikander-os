import { useEffect, useRef, useState } from 'react';
import ChatMessage from '../ChatMessage';
import { api } from '../api';

type Msg = { role: 'user' | 'assistant'; text: string; pairUserText?: string };

const STORAGE_KEY = 'igris.chat.history.v1';

function loadChat(): Msg[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length) return parsed;
    }
  } catch { /* ignore */ }
  return [{
    role: 'assistant',
    text: '**IGRIS online.** Systems nominal. State your directive, sir.',
  }];
}

type Props = {
  stream: boolean;
};

type PendingAction = { tool_name: string; tool_args: Record<string, any> };

export default function ChatConsole({ stream }: Props) {
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Msg[]>(loadChat);
  const [feedbackSent, setFeedbackSent] = useState<Record<number, boolean>>({});
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [pendingBusy, setPendingBusy] = useState(false);
  const boxRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshPendingAction = async () => {
    const data = await api.getPendingAction();
    if (data?.has_pending_action && data.pending_action) {
      setPendingAction(data.pending_action as PendingAction);
    } else {
      setPendingAction(null);
    }
  };

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)); } catch {}
  }, [messages]);

  useEffect(() => {
    const el = boxRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    refreshPendingAction();
    const id = window.setInterval(refreshPendingAction, 4000);
    return () => window.clearInterval(id);
  }, []);

  const handleFeedback = async (msgIndex: number, rating: -1 | 1) => {
    const m = messages[msgIndex];
    if (!m || m.role !== 'assistant' || !m.pairUserText || !m.text.trim()) return;
    const ok = await api.submitFeedback({
      user_message: m.pairUserText,
      igris_response: m.text,
      rating,
      model_used: 'chat',
    });
    if (ok?.success !== false && ok !== null) {
      setFeedbackSent((prev) => ({ ...prev, [msgIndex]: true }));
    }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    setMessages((p) => [...p, { role: 'user', text }]);
    setInput('');

    if (stream) {
      const userQuery = text;
      setMessages((p) => [...p, { role: 'assistant', text: '', pairUserText: userQuery }]);
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        await api.chatStream(text, (chunk) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === 'assistant') {
              next[next.length - 1] = { role: 'assistant', text: last.text + chunk };
            }
            return next;
          });
        }, ctrl.signal);
      } catch (err: any) {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          const msg = `⚠ Stream error: ${err?.message || 'failed'}`;
          if (last?.role === 'assistant' && !last.text) {
            next[next.length - 1] = { role: 'assistant', text: msg };
          } else {
            next.push({ role: 'assistant', text: msg });
          }
          return next;
        });
      } finally {
        abortRef.current = null;
        setBusy(false);
        refreshPendingAction();
      }
    } else {
      try {
        const reply = await api.chat(text);
        setMessages((p) => [...p, { role: 'assistant', text: reply, pairUserText: text }]);
      } catch (err: any) {
        setMessages((p) => [...p, { role: 'assistant', text: `Request failed: ${err?.message || 'unknown'}` }]);
      } finally {
        setBusy(false);
        refreshPendingAction();
      }
    }
  };

  const stop = () => { abortRef.current?.abort(); abortRef.current = null; setBusy(false); };
  const clear = () => setMessages([{ role: 'assistant', text: 'Log cleared. Awaiting orders.' }]);

  const approvePending = async () => {
    if (!pendingAction || pendingBusy) return;
    setPendingBusy(true);
    try {
      const res = await api.approvePendingAction();
      if (res?.ok) {
        setMessages((p) => [...p, { role: 'assistant', text: 'Approved and executed.' }]);
      } else {
        setMessages((p) => [...p, { role: 'assistant', text: `Approve failed: ${res?.error || 'unknown error'}` }]);
      }
    } finally {
      setPendingBusy(false);
      refreshPendingAction();
    }
  };

  const cancelPending = async () => {
    if (!pendingAction || pendingBusy) return;
    setPendingBusy(true);
    try {
      const res = await api.cancelPendingAction();
      setMessages((p) => [...p, { role: 'assistant', text: res?.ok ? 'Pending action cancelled.' : 'Cancel failed.' }]);
    } finally {
      setPendingBusy(false);
      refreshPendingAction();
    }
  };

  return (
    <div className="chat-console">
      {pendingAction ? (
        <div className="chat-console-pending" style={{ marginBottom: 8, padding: 10, border: '1px solid #7c2d12', borderRadius: 8 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Approval Required</div>
          <div style={{ fontSize: 12, opacity: 0.9, marginBottom: 8 }}>
            Tool: <code>{pendingAction.tool_name}</code> Args: <code>{JSON.stringify(pendingAction.tool_args)}</code>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={approvePending} disabled={pendingBusy}>Approve</button>
            <button onClick={cancelPending} disabled={pendingBusy} className="btn-ghost">Cancel</button>
          </div>
        </div>
      ) : null}
      <div className="chat-console-box" ref={boxRef}>
        {messages.map((m, i) => (
          <ChatMessage
            key={`${m.role}-${i}`}
            role={m.role}
            text={m.text}
            pairUserText={m.role === 'assistant' ? m.pairUserText : undefined}
            feedbackSent={feedbackSent[i]}
            feedbackDisabled={busy}
            onFeedback={
              m.role === 'assistant' && m.pairUserText
                ? (r) => handleFeedback(i, r)
                : undefined
            }
          />
        ))}
      </div>
      <div className="chat-console-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={busy ? 'Transmitting…' : 'Direct command to IGRIS…'}
          disabled={busy && !stream}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) send(); }}
        />
        {busy && stream ? (
          <button onClick={stop} className="btn-danger">HALT</button>
        ) : (
          <button onClick={send} disabled={busy || !input.trim()}>
            {busy ? 'SENDING' : 'TRANSMIT'}
          </button>
        )}
        <button onClick={clear} className="btn-ghost">CLEAR</button>
      </div>
    </div>
  );
}
