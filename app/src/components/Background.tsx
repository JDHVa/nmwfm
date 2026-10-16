import Galaxy from "@/components/Galaxy";
import Silk from "@/components/Silk";
import { useReducedMotion } from "@/lib/app-context";
import { useTheme } from "@/lib/theme";
import { token } from "@/lib/tokens";

export function Background() {
  const reducido = useReducedMotion();
  const { resuelto } = useTheme();

  if (resuelto === "oscuro") {
    return (
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <Galaxy
          key="galaxy"
          transparent
          density={0.35}
          starSpeed={0.15}
          speed={0.3}
          glowIntensity={0.12}
          saturation={0.25}
          hueShift={200}
          twinkleIntensity={0.2}
          opacity={0.55}
          dpr={0.75}
          disableAnimation={reducido}
          mouseInteraction={false}
          mouseRepulsion={false}
          clickWarp={false}
          intro={false}
        />
      </div>
    );
  }

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 opacity-30">
      <Silk
        key="silk"
        color={token("--silk", "#7ea6cf")}
        sheenColor={token("--silk-sheen", "#c4d6e0")}
        lightMode
        speed={0.4}
        noiseIntensity={0.35}
        depth={0.25}
        dpr={0.75}
        paused={reducido}
        mouseInteraction={false}
        clickRipple={false}
        intro={false}
      />
    </div>
  );
}
