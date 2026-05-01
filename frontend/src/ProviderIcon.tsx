import type { CSSProperties } from 'react';

/**
 * Provider visual identity: color + initial letter (no external assets).
 * Keeps the bundle tiny and works offline in Docker / PyWebView.
 */

export type ProviderVisual = {
  color: string;      // primary brand color
  fg: string;         // foreground text color
  letter: string;     // 1-2 char mark
};

const VISUALS: Record<string, ProviderVisual> = {
  ollama:      { color: '#2f3136', fg: '#ffffff', letter: 'O'  },
  openai:      { color: '#10a37f', fg: '#ffffff', letter: 'AI' },
  anthropic:   { color: '#cc785c', fg: '#ffffff', letter: 'C'  },
  gemini:      { color: '#4285f4', fg: '#ffffff', letter: 'G'  },
  groq:        { color: '#f55036', fg: '#ffffff', letter: 'Gq' },
  mistral:     { color: '#ff7000', fg: '#ffffff', letter: 'M'  },
  together:    { color: '#0f6fff', fg: '#ffffff', letter: 'T'  },
  openrouter:  { color: '#8a63f2', fg: '#ffffff', letter: 'OR' },
  perplexity:  { color: '#20808d', fg: '#ffffff', letter: 'Px' },
  huggingface: { color: '#ffd21e', fg: '#1a1a1a', letter: 'HF' },
};

const FALLBACK: ProviderVisual = { color: '#3b4252', fg: '#ffffff', letter: '?' };

export function getProviderVisual(provider: string): ProviderVisual {
  return VISUALS[provider] || FALLBACK;
}

type Props = {
  provider: string;
  size?: number;
  title?: string;
  style?: CSSProperties;
};

export function ProviderIcon({ provider, size = 20, title, style }: Props) {
  const v = getProviderVisual(provider);
  const font = Math.max(9, Math.round(size * 0.45));
  return (
    <span
      className="provider-icon"
      title={title || provider}
      style={{
        width: size,
        height: size,
        background: v.color,
        color: v.fg,
        fontSize: font,
        ...style,
      }}
    >
      {v.letter}
    </span>
  );
}
