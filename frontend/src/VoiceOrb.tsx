import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import './voice-orb-app.css';

const WAKE_WORDS = ['hey igris', 'igris', 'jarvis'];
const WAKE_KEY = 'igris.voice.wake.v1';
const LANG_KEY = 'igris.voice.lang.v1';

const DEFAULT_VOICE_LANG: string =
  (import.meta as any).env?.VITE_VOICE_LANG || 'en-US';

const LANG_OPTIONS: { code: string; label: string }[] = [
  { code: 'en-US', label: 'English (US)' },
  { code: 'ur-PK', label: 'Urdu / Roman (PK)' },
  { code: 'hi-IN', label: 'Hindi (IN)' },
];

function plainForTTS(s: string): string {
  return s.replace(/\*\*/g, '').replace(/`/g, '').slice(0, 8000);
}

type RecognitionState = {
  stream?: MediaStream;
  ctx?: AudioContext;
  analyser?: AnalyserNode;
  raf?: number;
};

/**
 * Floating Siri/JARVIS-style voice orb with:
 *  - Push-to-talk (click SPEAK)
 *  - Wake-word mode ("Hey Igris" / "Igris" / "Jarvis") — continuous listening
 *  - Text fallback for PyWebView / browsers without Web Speech API
 *  - Live audio-level visualiser while listening
 *  - TTS reply via speechSynthesis
 */
export type VoiceOrbProps = {
  /** Floating HUD orb (default) vs compact dock next to composer */
  variant?: 'float' | 'inline';
  /**
   * When set, voice SEND runs this (e.g. main chat stream) instead of standalone /chat + TTS.
   */
  onVoiceSubmit?: (text: string) => Promise<void>;
  /** Disable voice send while main chat is streaming */
  disabled?: boolean;
};

export default function VoiceOrb({ variant = 'float', onVoiceSubmit, disabled = false }: VoiceOrbProps) {
  const [open, setOpen] = useState(false);
  const [listening, setListening] = useState(false);
  const [wakeMode, setWakeMode] = useState<boolean>(() => {
    try { return localStorage.getItem(WAKE_KEY) === '1'; } catch { return false; }
  });
  const [voiceLang, setVoiceLang] = useState<string>(() => {
    try {
      const raw = localStorage.getItem(LANG_KEY);
      if (raw && LANG_OPTIONS.some((o) => o.code === raw)) return raw;
    } catch { /* ignore */ }
    return DEFAULT_VOICE_LANG;
  });
  const [supported, setSupported] = useState(true);
  const [text, setText] = useState('');
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState(0);
  const [wakeDetected, setWakeDetected] = useState(false);

  const recRef  = useRef<any>(null);
  const resRef  = useRef<RecognitionState>({});

  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setSupported(Boolean(SR));
  }, []);

  useEffect(() => {
    try { localStorage.setItem(WAKE_KEY, wakeMode ? '1' : '0'); } catch {}
  }, [wakeMode]);

  useEffect(() => {
    try { localStorage.setItem(LANG_KEY, voiceLang); } catch {}
  }, [voiceLang]);

  // Start wake-word recognition when toggled on
  useEffect(() => {
    if (!wakeMode) return;
    startWakeListening();
    return () => stopRecognition();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wakeMode]);

  useEffect(() => () => { stopRecognition(); teardownAudio(); }, []);

  const teardownAudio = () => {
    const s = resRef.current;
    if (s.raf) cancelAnimationFrame(s.raf);
    try { s.stream?.getTracks().forEach((t) => t.stop()); } catch {}
    try { s.ctx?.close(); } catch {}
    resRef.current = {};
  };

  const setupAudio = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      resRef.current = { stream, ctx, analyser };
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteFrequencyData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += buf[i];
        setLevel(Math.min(1, (sum / buf.length) / 120));
        resRef.current.raf = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      /* mic denied */
    }
  };

  const stopRecognition = () => {
    try { recRef.current?.stop?.(); } catch {}
    try { recRef.current?.abort?.(); } catch {}
    recRef.current = null;
  };

  // ── Push-to-talk (single-shot) ─────────────────────────────────
  const startListening = async () => {
    await setupAudio();
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setListening(false); return; }

    const rec = new SR();
    rec.lang = voiceLang;
    rec.interimResults = true;
    rec.continuous = false;
    recRef.current = rec;

    rec.onresult = (ev: any) => {
      let t = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) t += ev.results[i][0].transcript;
      setText(t);
      if (ev.results[ev.results.length - 1].isFinal) submit(t);
    };
    rec.onend   = () => { setListening(false); teardownAudio(); };
    rec.onerror = () => { setListening(false); };

    try { rec.start(); setListening(true); } catch { setListening(false); }
  };

  const stopListening = () => {
    stopRecognition();
    setListening(false);
    teardownAudio();
    if (wakeMode) setTimeout(startWakeListening, 300);
  };

  // ── Wake-word (continuous) ─────────────────────────────────────
  const startWakeListening = async () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    if (recRef.current) return;

    await setupAudio();

    const rec = new SR();
    rec.lang = voiceLang;
    rec.interimResults = true;
    rec.continuous = true;
    recRef.current = rec;
    setListening(true);

    let buffer = '';
    let armed = false;

    rec.onresult = (ev: any) => {
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        const chunk = r[0].transcript.toLowerCase();
        if (!armed) {
          // scan chunk for wake word
          const hit = WAKE_WORDS.find((w) => chunk.includes(w));
          if (hit) {
            armed = true;
            setWakeDetected(true);
            setOpen(true);
            setText('');
            buffer = chunk.split(hit).slice(1).join(hit).trim();
            setText(buffer);
            beep();
          }
        } else {
          if (r.isFinal) {
            buffer = (buffer + ' ' + r[0].transcript).trim();
            setText(buffer);
            armed = false;
            setWakeDetected(false);
            submit(buffer);
            buffer = '';
          } else {
            setText(((buffer + ' ' + r[0].transcript).trim()));
          }
        }
      }
    };

    rec.onend = () => {
      recRef.current = null;
      setListening(false);
      if (wakeMode) setTimeout(startWakeListening, 400);
    };
    rec.onerror = () => {
      recRef.current = null;
      setListening(false);
      if (wakeMode) setTimeout(startWakeListening, 1200);
    };

    try { rec.start(); } catch { /* already running */ }
  };

  // ── Submit + TTS ───────────────────────────────────────────────
  const submit = async (raw: string) => {
    const q = raw.trim();
    if (!q || busy || disabled) return;
    setBusy(true);
    setReply(null);
    try {
      if (onVoiceSubmit) {
        await onVoiceSubmit(q);
      } else {
        const r = await api.chat(q);
        setReply(r);
        speak(r);
      }
    } catch {
      setReply(onVoiceSubmit ? 'Channel error.' : 'Transmission failed.');
    } finally {
      setBusy(false);
    }
  };

  const speak = (msg: string) => {
    try {
      const s = window.speechSynthesis;
      if (!s) return;
      const u = new SpeechSynthesisUtterance(plainForTTS(msg));
      u.lang = voiceLang;
      u.rate = 1.05;
      u.pitch = 0.95;
      s.cancel();
      s.speak(u);
    } catch {}
  };

  const beep = () => {
    try {
      const ctx = resRef.current.ctx || new (window.AudioContext || (window as any).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = 880;
      gain.gain.value = 0.05;
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start();
      setTimeout(() => { osc.stop(); }, 110);
    } catch {}
  };

  const rootClass =
    variant === 'inline'
      ? `voice-root voice-root--inline${listening ? ' voice-root--listening' : ''}`
      : `voice-root voice-root--float${listening ? ' voice-root--listening' : ''}`;

  // ── UI ─────────────────────────────────────────────────────────
  return (
    <div className={rootClass}>
      <button
        type="button"
        className={`voice-orb ${open ? 'open' : ''} ${listening ? 'listening' : ''} ${wakeDetected ? 'wake' : ''}`}
        onClick={() => setOpen((v) => !v)}
        aria-label={variant === 'inline' ? 'Voice — docked mic HUD' : 'Voice — HUD orb'}
        title={variant === 'inline' ? 'Mic / Voice HUD (dock mode)' : 'Voice HUD'}
        style={{ ['--mic-level' as any]: level }}
      >
        <span className="voice-orb-halo" aria-hidden />
        <span className="voice-orb-wave voice-orb-wave--1" aria-hidden />
        <span className="voice-orb-wave voice-orb-wave--2" aria-hidden />
        <span className="voice-orb-wave voice-orb-wave--3" aria-hidden />
        <span className="voice-orb-marble" aria-hidden>
          <span className="voice-orb-marble-surface" />
        </span>
        <span className="voice-orb-glare" aria-hidden />
        {wakeMode && <span className="voice-orb-wake-dot" title="Wake-word active" />}
      </button>

      {open && (
        <div className="voice-panel">
          <header className="vp-head">
            <span className="vp-title">
              IGRIS · VOICE LINK
              {wakeDetected && <i className="vp-wake-tag">◉ WAKE</i>}
            </span>
            <button className="vp-close" onClick={() => setOpen(false)}>✕</button>
          </header>

          {!supported && (
            <div className="vp-warn">
              Speech recognition not supported in this browser. You can still type below.
            </div>
          )}

          {supported ? (
            <div className="vp-lang-row">
              <label className="vp-lang-label" htmlFor="igris-voice-lang">Speech language</label>
              <select
                id="igris-voice-lang"
                className="vp-lang-select"
                value={voiceLang}
                onChange={(e) => setVoiceLang(e.target.value)}
                title="Web Speech API — use Chrome or Edge for best Urdu/Hindi support"
              >
                {LANG_OPTIONS.map((o) => (
                  <option key={o.code} value={o.code}>{o.label}</option>
                ))}
              </select>
            </div>
          ) : null}

          <div className="vp-levels">
            {Array.from({ length: 24 }, (_, i) => (
              <span
                key={i}
                className="vp-bar"
                style={{
                  height: `${6 + (listening ? level * 36 * (0.35 + Math.sin(i / 2 + Date.now() / 200) * 0.35) : 3)}px`,
                }}
              />
            ))}
          </div>

          <div className="vp-transcript">
            {text || (listening ? (wakeMode ? 'Listening for "Hey Igris"…' : 'Listening…') : 'Idle')}
          </div>

          <div className="vp-actions">
            {!listening || wakeMode ? (
              <button
                className="vp-btn primary"
                onClick={() => { if (wakeMode) return; startListening(); }}
                disabled={wakeMode}
                title={wakeMode ? 'Wake-word mode is active' : 'Push to talk'}
              >
                {supported ? 'SPEAK' : 'MIC'}
              </button>
            ) : (
              <button className="vp-btn danger" onClick={stopListening}>STOP</button>
            )}
            <input
              className="vp-input"
              placeholder="Or type command…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') submit(text); }}
            />
            <button className="vp-btn" disabled={busy || disabled} onClick={() => submit(text)}>
              {busy ? '…' : 'SEND'}
            </button>
          </div>

          {supported && (
            <label className="vp-wake-toggle" title='Say "Hey Igris", "Igris", or "Jarvis" to trigger'>
              <input
                type="checkbox"
                checked={wakeMode}
                onChange={(e) => setWakeMode(e.target.checked)}
              />
              <span>WAKE-WORD · "Hey Igris"</span>
            </label>
          )}

          {reply && !onVoiceSubmit && (
            <div className="vp-reply">
              <div className="vp-reply-label">IGRIS</div>
              <div className="vp-reply-text">{reply}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
