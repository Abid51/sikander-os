import { useCallback, useEffect, useState } from 'react';

export type Msg = { role: 'user' | 'assistant'; text: string; ts: number };
export type ChatSession = {
  id: string;
  title: string;
  messages: Msg[];
  updated: number;
};

const KEY = 'igris.chats.v2';

function load(): ChatSession[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
  } catch { /* ignore */ }
  return [];
}

function save(list: ChatSession[]) {
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch {}
}

export function useChats() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => load());
  const [activeId, setActiveId] = useState<string | null>(() => {
    const l = load();
    return l.length ? l[0].id : null;
  });

  useEffect(() => { save(sessions); }, [sessions]);

  const active = sessions.find((s) => s.id === activeId) || null;

  const createChat = useCallback(() => {
    const s: ChatSession = {
      id: Math.random().toString(36).slice(2),
      title: 'New chat',
      messages: [],
      updated: Date.now(),
    };
    setSessions((cur) => [s, ...cur]);
    setActiveId(s.id);
    return s.id;
  }, []);

  const openChat = useCallback((id: string) => setActiveId(id), []);

  const deleteChat = useCallback((id: string) => {
    setSessions((cur) => cur.filter((s) => s.id !== id));
    setActiveId((cur) => {
      if (cur !== id) return cur;
      const next = load().filter((s) => s.id !== id);
      return next.length ? next[0].id : null;
    });
  }, []);

  const appendMessage = useCallback((id: string, msg: Msg) => {
    setSessions((cur) =>
      cur.map((s) => {
        if (s.id !== id) return s;
        const next = { ...s, messages: [...s.messages, msg], updated: Date.now() };
        if (s.messages.length === 0 && msg.role === 'user') {
          next.title = msg.text.slice(0, 42);
        }
        return next;
      })
    );
  }, []);

  const updateLastAssistant = useCallback(
    (id: string, updater: (cur: string) => string) => {
      setSessions((cur) =>
        cur.map((s) => {
          if (s.id !== id) return s;
          const msgs = [...s.messages];
          const last = msgs[msgs.length - 1];
          if (last && last.role === 'assistant') {
            msgs[msgs.length - 1] = { ...last, text: updater(last.text) };
          }
          return { ...s, messages: msgs, updated: Date.now() };
        })
      );
    },
    []
  );

  return {
    sessions,
    active,
    activeId,
    createChat,
    openChat,
    deleteChat,
    appendMessage,
    updateLastAssistant,
  };
}
