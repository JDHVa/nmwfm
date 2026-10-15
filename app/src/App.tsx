import { useEffect } from "react";
import { BookOpen, Settings as SettingsIcon } from "lucide-react";
import Dock from "@/components/Dock";
import { Background } from "@/components/Background";
import { LogPanel } from "@/components/LogPanel";
import { NavProvider, useNav, useReducedMotion } from "@/lib/app-context";
import { useSettings } from "@/lib/queries";
import { ConfigView } from "@/views/ConfigView";
import { MateriaView } from "@/views/MateriaView";
import { MateriasView } from "@/views/MateriasView";
import { TareaView } from "@/views/TareaView";

function Shell({ primerArranque }: { primerArranque: boolean }) {
  const { view, go } = useNav();
  const reducido = useReducedMotion();

  useEffect(() => {
    document.documentElement.classList.toggle("reduce-motion", reducido);
  }, [reducido]);

  const enMaterias = view.name === "materias" || view.name === "materia" || view.name === "tarea";

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      <Background />
      <div className="relative z-10 flex min-h-0 flex-1">
        <nav aria-label="Navegación" className="relative w-24 shrink-0">
          {!primerArranque && (
            <Dock
              position="left"
              theme="dark"
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
              ]}
            />
          )}
        </nav>
        <main className="min-w-0 flex-1 overflow-y-auto">
          {view.name === "config" && <ConfigView primerArranque={primerArranque} />}
          {view.name === "materias" && <MateriasView />}
          {view.name === "materia" && <MateriaView id={view.id} />}
          {view.name === "tarea" && <TareaView id={view.id} materiaId={view.materiaId} />}
        </main>
      </div>
      <LogPanel />
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
  const primerArranque = !settings.cuenta;
  return (
    <NavProvider initial={{ name: primerArranque ? "config" : "materias" }}>
      <Shell primerArranque={primerArranque} />
    </NavProvider>
  );
}
