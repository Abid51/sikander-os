import { useEffect, useRef } from 'react';

type Props = {
  density?: number;
  speed?: number;
  color?: string;
};

/**
 * Wireframe / particle background evoking the Tony Stark lab HUD:
 * subtle drifting dots + radial pulse lines. Canvas-based, pointer-events: none.
 */
export default function WireframeBackground({
  density = 65,
  speed = 0.3,
  color = 'rgba(138, 223, 255, 0.75)',
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = canvas.width = window.innerWidth;
    let h = canvas.height = window.innerHeight;

    type P = { x: number; y: number; vx: number; vy: number; r: number; a: number };
    const parts: P[] = Array.from({ length: density }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * speed,
      vy: (Math.random() - 0.5) * speed,
      r: Math.random() * 1.6 + 0.4,
      a: Math.random() * 0.6 + 0.2,
    }));

    const resize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', resize);

    let raf = 0;
    const loop = () => {
      ctx.clearRect(0, 0, w, h);

      // thin diagonal pulses
      ctx.strokeStyle = 'rgba(138, 223, 255, 0.04)';
      ctx.lineWidth = 1;
      for (let i = 0; i < 6; i++) {
        const y = ((performance.now() / 40 + i * h / 6) % h);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y + 30);
        ctx.stroke();
      }

      // particles + connecting lines
      for (const p of parts) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = color.replace('0.75', String(p.a));
        ctx.fill();
      }

      // connection lines
      for (let i = 0; i < parts.length; i++) {
        for (let j = i + 1; j < parts.length; j++) {
          const a = parts[i], b = parts[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < 140 * 140) {
            const alpha = (1 - Math.sqrt(d2) / 140) * 0.22;
            ctx.strokeStyle = `rgba(138, 223, 255, ${alpha})`;
            ctx.lineWidth = 0.6;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, [color, density, speed]);

  return <canvas ref={canvasRef} className="hud-wireframe" aria-hidden />;
}
