import Silk from "@/components/Silk";
import { useReducedMotion } from "@/lib/app-context";
import { token } from "@/lib/tokens";

export function Background() {
  const reducido = useReducedMotion();
  if (reducido) {
    return (
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(160deg,var(--silk),var(--background)_55%,var(--silk-sheen))] opacity-60"
      />
    );
  }
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 opacity-60">
      <Silk
        color={token("--silk", "#93c5fd")}
        sheenColor={token("--silk-sheen", "#a5f3fc")}
        lightMode
        speed={1}
        mouseInteraction={false}
        clickRipple={false}
      />
    </div>
  );
}
