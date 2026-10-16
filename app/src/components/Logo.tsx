export function Logo({ className = "size-12" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="Logo de nmwfm">
      <path d="M32 8 3 22l29 14 29-14L32 8Z" fill="var(--primary)" />
      <path d="M14 31v13c0 4 8 9 18 9s18-5 18-9V31L32 39 14 31Z" fill="var(--primary)" opacity="0.8" />
      <path d="M56 24v18" stroke="var(--foreground)" strokeWidth="3" strokeLinecap="round" />
      <circle cx="56" cy="45" r="3.5" fill="var(--foreground)" />
    </svg>
  );
}
