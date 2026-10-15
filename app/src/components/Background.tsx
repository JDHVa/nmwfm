import Aurora from "@/components/Aurora";
import { useReducedMotion } from "@/lib/app-context";

export function Background() {
  const reducido = useReducedMotion();
  if (reducido) {
    return (
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-0 bg-[radial-gradient(ellipse_at_top,oklch(0.25_0.05_285),transparent_60%)]"
      />
    );
  }
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-0 opacity-60">
      <Aurora
        colorStops={["#4c3bd6", "#2a7fd6", "#7a3fd6"]}
        amplitude={0.9}
        blend={0.6}
        speed={0.5}
        mouseInteraction={false}
      />
    </div>
  );
}
