import Galaxy from "@/components/Galaxy";
import Silk from "@/components/Silk";
import { useReducedMotion } from "@/lib/app-context";
import { useTheme } from "@/lib/theme";
import { token } from "@/lib/tokens";

export function Background() {
  const reducido = useReducedMotion();
  const { resuelto } = useTheme();

  if (reducido) {
    return (
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(160deg,var(--silk),var(--background)_55%,var(--silk-sheen))] opacity-60 [[data-theme=dark]_&]:bg-[radial-gradient(ellipse_at_top,rgb(99_102_241/0.35),var(--background)_70%)] [[data-theme=dark]_&]:opacity-100"
      />
    );
  }

  if (resuelto === "oscuro") {
    return (
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <Galaxy
          transparent
          density={0.8}
          starSpeed={0.3}
          speed={0.6}
          glowIntensity={0.25}
          saturation={0.6}
          hueShift={200}
          mouseInteraction={false}
          mouseRepulsion={false}
        />
      </div>
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
