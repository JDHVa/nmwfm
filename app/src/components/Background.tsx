import Silk from "@/components/Silk";
import { useReducedMotion } from "@/lib/app-context";
import { useTheme } from "@/lib/theme";
import { token } from "@/lib/tokens";

export function Background() {
  const reducido = useReducedMotion();
  const { resuelto } = useTheme();

  if (resuelto === "oscuro") {
    return (
      <div aria-hidden className={reducido ? "sky-static" : undefined}>
        <div className="sky" />
        <div className="sky-stars sky-stars-a" />
        <div className="sky-stars sky-stars-b" />
        <div className="sky-stars sky-stars-c" />
      </div>
    );
  }

  if (reducido) {
    return (
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(160deg,var(--silk),var(--background)_55%,var(--silk-sheen))] opacity-60"
      />
    );
  }

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 opacity-45">
      <Silk
        color={token("--silk", "#60b0ff")}
        sheenColor={token("--silk-sheen", "#a5f3fc")}
        lightMode
        speed={1}
        noiseIntensity={0.6}
        depth={0.4}
        mouseInteraction={false}
        clickRipple={false}
      />
    </div>
  );
}
