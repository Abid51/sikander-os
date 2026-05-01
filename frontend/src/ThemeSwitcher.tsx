import { THEMES, useTheme, type ThemeId } from './ThemeLayout';

/**
 * Compact 3-dot theme cycler. Shows all three themes as mini swatches;
 * clicking the current one advances to next. Hover label shows mode.
 */
export default function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="theme-switcher" title={`Mode · ${THEMES[theme].label}`}>
      {(['azure', 'crimson', 'emerald', 'operator'] as ThemeId[]).map((t) => (
        <button
          key={t}
          type="button"
          className={`ts-swatch ts-${t} ${theme === t ? 'active' : ''}`}
          onClick={() => setTheme(t)}
          aria-label={`Switch to ${THEMES[t].label} mode`}
          title={`${THEMES[t].label} · ${THEMES[t].glyph}`}
        >
          <span>{THEMES[t].icon}</span>
        </button>
      ))}
    </div>
  );
}
