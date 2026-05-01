import { useEffect, useState } from 'react';
import { FpsCounter, MiniClock } from './hud/MicroHud';

type Props = {
  onOpenPalette: () => void;
};

/**
 * Slim bottom footer: hotkeys, fullscreen toggle, clock, fps.
 * Replaces the need for verbose labels elsewhere.
 */
export default function HotkeyFooter({ onOpenPalette }: Props) {
  const [fs, setFs] = useState(false);

  useEffect(() => {
    const h = () => setFs(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', h);
    return () => document.removeEventListener('fullscreenchange', h);
  }, []);

  const toggleFs = () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  };

  return (
    <div className="hotkey-footer">
      <div className="hk-left">
        <button className="hk-pill" onClick={onOpenPalette}>
          <kbd>Ctrl</kbd><kbd>K</kbd> COMMAND
        </button>
        <span className="hk-pill static"><kbd>⏎</kbd> TRANSMIT</span>
        <span className="hk-pill static"><kbd>Esc</kbd> CLOSE</span>
        <button className="hk-pill" onClick={toggleFs}>
          {fs ? '◉ EXIT FULLSCREEN' : '◈ FULLSCREEN'}
        </button>
      </div>
      <div className="hk-right">
        <MiniClock />
        <FpsCounter />
      </div>
    </div>
  );
}
