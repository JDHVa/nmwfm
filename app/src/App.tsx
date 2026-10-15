import { useEffect, useState } from "react";
import { BookOpen, LogOut, Settings as SettingsIcon } from "lucide-react";
import Dock from "@/components/Dock";
import { Background } from "@/components/Background";
import { LogPanel } from "@/components/LogPanel";
import { NavProvider, useNav, useReducedMotion } from "@/lib/app-context";
import type { Settings } from "@/lib/api";
import { useSettings } from "@/lib/queries";
import { leerRecordar } from "@/lib/session";
import { token } from "@/lib/tokens";
import { ConfigView } from "@/views/ConfigView";
import { LoginView } from "@/views/LoginView";
import { MateriaView } from "@/views/MateriaView";
import { MateriasView } from "@/views/MateriasView";
import { SaludoView } from "@/views/SaludoView";
import { TareaView } from "@/views/TareaView";

function Shell({ onSalir }: { onSalir: () => void }) {
  const { view, go } = useNav();
  const enMaterias = view.name === "materias" || view.name === "materia" || view.name === "tarea";

  return (
    <div className="relative z-10 flex h-full flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1">
        <nav aria-label="Navegación" className="relative w-24 shrink-0">
          <Dock
            position="left"
            theme="light"
            accentColor={token("--primary")}
            showLabels
            items={[
              {
                label: "Materias",
                icon: <BookOpen className="size-5" />,
                active: enMaterias,
                onClick: () => go({ name: "materias" }),
              },
              {
                label: "Configuración",
                icon: <SettingsIcon className="size-5" />,
                active: view.name === "config",
                onClick: () => go({ name: "config" }),
              },
              {
                label: "Cerrar sesión",
                icon: <LogOut className="size-5" />,
                onClick: onSalir,
              },
            ]}
          />
        </nav>
        <main className="min-w-0 flex-1 overflow-y-auto">
          {view.name === "config" && <ConfigView />}
          {view.name === "materias" && <MateriasView />}
          {view.name === "materia" && <MateriaView id={view.id} />}
          {view.name === "tarea" && <TareaView id={view.id} materiaId={view.materiaId} />}
        </main>
      </div>
      <LogPanel />
    </div>
  );
}

type Fase = "login" | "saludo" | "app";

function Raiz({ settings }: { settings: Settings }) {
  const reducido = useReducedMotion();
  const [fase, setFase] = useState<Fase>(() =>
    leerRecordar() && settings.cuenta && settings.tiene_password ? "saludo" : "login",
  );

  useEffect(() => {
    document.documentElement.classList.toggle("reduce-motion", reducido);
  }, [reducido]);

  return (
    <div className="relative h-full overflow-hidden">
      <Background />
      <div className="relative z-10 h-full">
        {fase === "login" && <LoginView settings={settings} onEntrar={() => setFase("app")} />}
        {fase === "saludo" && <SaludoView nombre={settings.nombre} onTerminar={() => setFase("app")} />}
        {fase === "app" && (
          <NavProvider initial={{ name: "materias" }}>
            <Shell onSalir={() => setFase("login")} />
          </NavProvider>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const { data: settings, isLoading, error } = useSettings();

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Conectando con el servicio local…
      </div>
    );
  }
  if (error || !settings) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <p className="text-lg font-semibold">No se pudo conectar con el servicio local</p>
        <p className="text-sm text-muted-foreground">{error?.message ?? "Reintentando…"}</p>
      </div>
    );
  }
  return <Raiz settings={settings} />;
}
