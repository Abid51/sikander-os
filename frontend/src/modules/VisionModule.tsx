import { useEffect, useState } from 'react';
import { api } from '../api';

export default function VisionModule() {
  const [status, setStatus] = useState<any>({});
  const [capture, setCapture] = useState<any>(null);
  const [ocr, setOcr] = useState<any>(null);
  const [busy, setBusy] = useState<'' | 'cap' | 'ocr'>('');

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const s = await api.aetherStatus();
      if (alive) setStatus(s || {});
    };
    load();
    const t = setInterval(load, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const onCapture = async () => {
    setBusy('cap');
    const r = await api.captureScreen();
    setCapture(r);
    setBusy('');
  };

  const onOcr = async () => {
    setBusy('ocr');
    const r = await api.ocrScreen();
    setOcr(r);
    setBusy('');
  };

  return (
    <div className="vision-module">
      <div className="vision-eye">
        <div className="eye-outer">
          <div className="eye-iris">
            <div className="eye-pupil" />
            <div className="eye-scan" />
          </div>
        </div>
        <div className="eye-caption">AETHER EYE</div>
      </div>

      <div className="vision-stats">
        <div>
          <span>STATUS</span>
          <b className={status?.online ? 'ok' : 'warn'}>
            {status?.online ? 'ONLINE' : (status?.status || 'IDLE')}
          </b>
        </div>
        <div>
          <span>LAST CAPTURE</span>
          <b>{capture?.timestamp ? new Date(capture.timestamp).toLocaleTimeString() : '—'}</b>
        </div>
        <div>
          <span>OCR TOKENS</span>
          <b>{ocr?.text ? ocr.text.split(/\s+/).length : 0}</b>
        </div>
      </div>

      <div className="vision-actions">
        <button disabled={!!busy} onClick={onCapture}>
          {busy === 'cap' ? 'CAPTURING…' : 'CAPTURE SCREEN'}
        </button>
        <button disabled={!!busy} onClick={onOcr}>
          {busy === 'ocr' ? 'SCANNING…' : 'OCR SCAN'}
        </button>
      </div>

      {ocr?.text && (
        <div className="vision-ocr-out">
          <div className="vo-head">OCR OUTPUT</div>
          <div className="vo-body">{String(ocr.text).slice(0, 300)}</div>
        </div>
      )}
    </div>
  );
}
