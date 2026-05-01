import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type ThemeId = 'azure' | 'crimson' | 'emerald' | 'operator';

export const THEMES: Record<ThemeId, { label: string; icon: string; glyph: string }> = {
  azure:    { label: 'AZURE',    icon: '◈', glyph: 'Standard Ops'  },
  crimson:  { label: 'CRIMSON',  icon: '⛨', glyph: 'War Mode'      },
  emerald:  { label: 'EMERALD',  icon: '◉', glyph: 'Stealth'       },
  operator: { label: 'OPERATOR', icon: '▣', glyph: 'Tactical Grid' },
};

const THEME_KEY = 'igris.theme.v1';
const LAYOUT_KEY = 'igris.layout.v1';

// ─── Theme context ───────────────────────────────────────────────────────

type ThemeCtx = {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
  cycle: () => void;
};

const ThemeContext = createContext<ThemeCtx>({
  theme: 'azure',
  setTheme: () => {},
  cycle: () => {},
});

export function useTheme() { return useContext(ThemeContext); }

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    try {
      const v = localStorage.getItem(THEME_KEY);
      if (v === 'azure' || v === 'crimson' || v === 'emerald') return v;
    } catch { /* ignore */ }
    return 'azure';
  });

  useEffect(() => {
    try { localStorage.setItem(THEME_KEY, theme); } catch {}
    document.body.dataset.theme = theme;
  }, [theme]);

  const setTheme = (t: ThemeId) => setThemeState(t);
  const cycle = () => {
    setThemeState((cur) => {
      const order: ThemeId[] = ['azure', 'crimson', 'emerald', 'operator'];
      return order[(order.indexOf(cur) + 1) % order.length];
    });
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, cycle }}>
      {children}
    </ThemeContext.Provider>
  );
}

// ─── Layout (per-panel minimize state) ──────────────────────────────────

type PanelState = { minimized: boolean };
type LayoutMap = Record<string, PanelState>;

type LayoutCtx = {
  layout: LayoutMap;
  toggle: (id: string) => void;
  isMinimized: (id: string) => boolean;
  reset: () => void;
};

const LayoutContext = createContext<LayoutCtx>({
  layout: {},
  toggle: () => {},
  isMinimized: () => false,
  reset: () => {},
});

export function useLayout() { return useContext(LayoutContext); }

export function LayoutProvider({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState<LayoutMap>(() => {
    try {
      const raw = localStorage.getItem(LAYOUT_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') return parsed as LayoutMap;
      }
    } catch { /* ignore */ }
    return {};
  });

  useEffect(() => {
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)); } catch {}
  }, [layout]);

  const toggle = (id: string) => {
    setLayout((cur) => ({
      ...cur,
      [id]: { minimized: !cur[id]?.minimized },
    }));
  };
  const isMinimized = (id: string) => Boolean(layout[id]?.minimized);
  const reset = () => setLayout({});

  return (
    <LayoutContext.Provider value={{ layout, toggle, isMinimized, reset }}>
      {children}
    </LayoutContext.Provider>
  );
}
