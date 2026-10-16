import { useEffect, useState } from "react";
import {
  BookOpen,
  CalendarClock,
  Search,
  LogOut,
  Monitor,
  Moon,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";
import Dock from "@/components/Dock";
import { Background } from "@/components/Background";
import { AyudaAtajos } from "@/components/AyudaAtajos";
import { Campanita } from "@/components/Campanita";
import { LogPanel } from "@/components/LogPanel";
import { PaletaBusqueda } from "@/components/PaletaBusqueda";
import { SyncIndicator, SyncOverlay } from "@/components/SyncStatus";
import { siguienteTema } from "@/components/ThemeToggle";
import { estaEscribiendo } from "@/lib/atajos";
import { escucharSyncDeBandeja, sincronizarPreferenciaConRust } from "@/lib/bandeja";
import { useAlertas } from "@/lib/alertas";
import { NavProvider, useNav, useReducedMotion } from "@/lib/app-context";
import type { Settings } from "@/lib/api";
import { useSettings } from "@/lib/queries";
import { leerRecordar } from "@/lib/session";
import { SyncProvider, useSync } from "@/lib/sync";
import { ETIQUETA_TEMA, useTheme } from "@/lib/theme";
import { token } from "@/lib/tokens";
import { ConfigView } from "@/views/ConfigView";
import { LoginView } from "@/views/LoginView";
import { MateriaView } from "@/views/MateriaView";
import { MateriasView } from "@/views/MateriasView";
import { ProximasView } from "@/views/ProximasView";
import { SaludoView } from "@/views/SaludoView";
import { TareaView } from "@/views/TareaView";

function Shell({ onSalir }: { onSalir: () => void }) {
  const { view, go } = useNav();
  const [buscando, setBuscando] = useState(false);
  const [ayuda, setAyuda] = useState(false);
  useAlertas();
  const sync = useSync();
  const iniciarSync = sync.iniciar;

  useEffect(() => {
    void sincronizarPreferenciaConRust();
    let quitar = () => {};
    let vivo = true;
    void escucharSyncDeBandeja(() => void iniciarSync("incremental")).then((fn) => {
      if (vivo) quitar = fn;
      else fn();
    });
    return () => {
      vivo = false;
      quitar();
    };
  }, [iniciarSync]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setBuscando((v) => !v);
      } else if (e.key === "?" && !e.ctrlKey && !e.metaKey && !estaEscribiendo(e.target)) {
        e.preventDefault();
        setAyuda((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const { tema, resuelto, setTema } = useTheme();
  const IconoTema = tema === "sistema" ? Monitor : tema === "claro" ? Sun : Moon;
  const enMaterias = view.name === "materias" || view.name === "materia" || view.name === "tarea";

  return (
    <div className="relative z-10 flex h-full flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1">
        <nav aria-label="Navegación" className="relative w-24 shrink-0">
          <Dock
            position="left"
            theme={resuelto === "oscuro" ? "dark" : "light"}
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
                label: "Próximas entregas",
                icon: <CalendarClock className="size-5" />,
                active: view.name === "proximas",
                onClick: () => go({ name: "proximas" }),
              },
              {
                label: "Configuración",
                icon: <SettingsIcon className="size-5" />,
                active: view.name === "config",
                onClick: () => go({ name: "config" }),
              },
              {
                label: `Tema: ${ETIQUETA_TEMA[tema]}`,
                icon: <IconoTema className="size-5" />,
                onClick: () => setTema(siguienteTema(tema)),
              },
              {
                label: "Cerrar sesión",
                icon: <LogOut className="size-5" />,
                onClick: onSalir,
              },
            ]}
          />
        </nav>
        <main className="relative min-w-0 flex-1 overflow-y-auto">
          <div className="absolute right-6 top-4 z-20 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setBuscando(true)}
              className="flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs font-medium shadow-card outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Search className="size-3.5" /> Buscar
              <kbd className="rounded border px-1 text-[10px] text-muted-foreground">Ctrl K</kbd>
            </button>
            <Campanita />
            <SyncIndicator />
          </div>
          <AyudaAtajos abierto={ayuda} onCerrar={() => setAyuda(false)} />
          <PaletaBusqueda abierto={buscando} onCerrar={() => setBuscando(false)} />
          {view.name === "config" && <ConfigView />}
          {view.name === "materias" && <MateriasView />}
          {view.name === "proximas" && <ProximasView />}
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
            <SyncProvider>
              <Shell onSalir={() => setFase("login")} />
              <SyncOverlay />
            </SyncProvider>
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
