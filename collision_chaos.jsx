import React, { useEffect, useRef } from "react";

// Canvas demo with wall + ball–ball collision physics
export default function ChaosCanvasColliding() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const WIDTH = 500;
  const HEIGHT = 500;
  const BALL_COUNT = 5; // keep light; raise for more chaos

  useEffect(() => {
    const canvas = canvasRef.current!;
    const dpr = Math.max(window.devicePixelRatio || 1, 1);

    canvas.width = WIDTH * dpr;
    canvas.height = HEIGHT * dpr;
    canvas.style.width = WIDTH + "px";
    canvas.style.height = HEIGHT + "px";

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    type Ball = {
      x: number;
      y: number;
      dx: number;
      dy: number;
      r: number;
      m: number; // mass ~ r^2
      color: string;
    };

    const rand = (min: number, max: number) => Math.random() * (max - min) + min;
    const colors = ["#FF00FF", "#00FF00", "#FFFF00", "#FF4500", "#1E90FF"];

    const balls: Ball[] = Array.from({ length: BALL_COUNT }, () => {
      const r = rand(15, 30);
      return {
        x: rand(r, WIDTH - r),
        y: rand(r, HEIGHT - r),
        dx: rand(-4, 4) || 2,
        dy: rand(-4, 4) || 3,
        r,
        m: r * r,
        color: colors[Math.floor(Math.random() * colors.length)],
      } as Ball;
    });

    const draw = () => {
      ctx.fillStyle = "#00FFFF"; // background cyan
      ctx.fillRect(0, 0, WIDTH, HEIGHT);

      balls.forEach((b) => {
        ctx.fillStyle = b.color;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();
      });
    };

    const step = () => {
      // integrate and handle walls
      balls.forEach((b) => {
        b.x += b.dx;
        b.y += b.dy;

        // wall collisions with simple restitution
        if (b.x - b.r < 0) { b.x = b.r; b.dx = -b.dx; }
        else if (b.x + b.r > WIDTH) { b.x = WIDTH - b.r; b.dx = -b.dx; }
        if (b.y - b.r < 0) { b.y = b.r; b.dy = -b.dy; }
        else if (b.y + b.r > HEIGHT) { b.y = HEIGHT - b.r; b.dy = -b.dy; }
      });

      // pairwise circle–circle collisions
      for (let i = 0; i < balls.length; i++) {
        for (let j = i + 1; j < balls.length; j++) {
          const a = balls[i];
          const b = balls[j];

          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.hypot(dx, dy) || 1e-8;
          const minDist = a.r + b.r;

          if (dist < minDist) {
            // collision normal
            const nx = dx / dist;
            const ny = dy / dist;

            // push them apart by overlap proportionally by mass
            const overlap = minDist - dist;
            const totalM = a.m + b.m;
            const sepA = overlap * (b.m / totalM);
            const sepB = overlap * (a.m / totalM);
            a.x -= nx * sepA; a.y -= ny * sepA;
            b.x += nx * sepB; b.y += ny * sepB;

            // relative velocity along normal
            const dvx = b.dx - a.dx;
            const dvy = b.dy - a.dy;
            const relVel = dvx * nx + dvy * ny;

            if (relVel < 0) {
              const e = 0.98; // near-elastic
              const jImpulse = (-(1 + e) * relVel) / (1 / a.m + 1 / b.m);
              const ix = jImpulse * nx;
              const iy = jImpulse * ny;
              a.dx -= ix / a.m; a.dy -= iy / a.m;
              b.dx += ix / b.m; b.dy += iy / b.m;
            }
          }
        }
      }
    };

    let raf = 0;
    const loop = () => {
      step();
      draw();
      raf = requestAnimationFrame(loop);
    };

    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className="w-full h-full min-h-[420px] flex items-center justify-center bg-neutral-900">
      <canvas
        ref={canvasRef}
        className="rounded-2xl shadow-xl border border-neutral-800"
        aria-label="BallPit"
      />
    </div>
  );
}
