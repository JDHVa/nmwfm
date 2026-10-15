import { useId } from "react";

export function Logo({ className = "size-12" }: { className?: string }) {
  const id = useId();
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="Logo de nmwfm">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--grad-from)" />
          <stop offset="1" stopColor="var(--grad-to)" />
        </linearGradient>
      </defs>
      <path d="M32 8 3 22l29 14 29-14L32 8Z" fill={`url(#${id})`} />
      <path d="M14 31v13c0 4 8 9 18 9s18-5 18-9V31L32 39 14 31Z" fill={`url(#${id})`} opacity="0.85" />
      <path d="M56 24v18" stroke="var(--mint)" strokeWidth="3" strokeLinecap="round" />
      <circle cx="56" cy="45" r="3.5" fill="var(--mint)" />
    </svg>
  );
}
