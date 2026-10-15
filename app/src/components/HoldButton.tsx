import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function HoldButton({
  children,
  onComplete,
  duration = 1500,
  className,
}: {
  children: ReactNode;
  onComplete: () => void;
  duration?: number;
  className?: string;
}) {
  const [progress, setProgress] = useState(0);
  const raf = useRef(0);
  const start = useRef(0);
  const done = useRef(false);
  const complete = useRef(onComplete);
  useEffect(() => {
    complete.current = onComplete;
  });

  const cancel = useCallback(() => {
    cancelAnimationFrame(raf.current);
    setProgress(0);
  }, []);

  const begin = useCallback(() => {
    done.current = false;
    start.current = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - start.current) / duration);
      setProgress(p);
      if (p >= 1) {
        if (!done.current) {
          done.current = true;
          complete.current();
        }
        setProgress(0);
        return;
      }
      raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
  }, [duration]);

  useEffect(() => () => cancelAnimationFrame(raf.current), []);

  return (
    <button
      type="button"
      onPointerDown={begin}
      onPointerUp={cancel}
      onPointerLeave={cancel}
      onPointerCancel={cancel}
      onKeyDown={(e) => {
        if ((e.key === " " || e.key === "Enter") && !e.repeat) begin();
      }}
      onKeyUp={cancel}
      onBlur={cancel}
      className={cn(
        "relative inline-flex h-9 select-none items-center justify-center overflow-hidden rounded-md border border-destructive/60 bg-destructive/10 px-4 text-sm font-medium text-destructive outline-none focus-visible:ring-[3px] focus-visible:ring-destructive/40",
        className,
      )}
    >
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 bg-destructive/40"
        style={{ width: `${progress * 100}%` }}
      />
      <span className="relative">{children}</span>
    </button>
  );
}
