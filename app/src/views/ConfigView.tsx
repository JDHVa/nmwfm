import { useState, type FormEvent } from "react";
import { LogIn, Save, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { HoldButton } from "@/components/HoldButton";
import { JobProgress } from "@/components/JobProgress";
import { api, type Settings } from "@/lib/api";
import { PasswordInput } from "@/components/PasswordInput";
import { useJobRunner, useSaveSettings, useSettings } from "@/lib/queries";
import { PageHeader } from "@/components/PageHeader";
import { aplicarCerrarABandeja, leerCerrarABandeja } from "@/lib/bandeja";
import { ConfigAvanzada } from "@/views/ConfigAvanzada";
import { ThemeSelector } from "@/components/ThemeToggle";

export function ConfigView() {
  const { data: settings } = useSettings();
  if (!settings) return <p className="p-8 text-muted-foreground">Cargando configuración…</p>;
  return <ConfigForm settings={settings} />;
}

function ConfigForm({ settings }: { settings: Settings }) {
  const guardar = useSaveSettings();
  const gemini = useJobRunner();
  const [form, setForm] = useState({
    cuenta: settings.cuenta,
    password: "",
    nombre: settings.nombre,
    matricula: settings.matricula,
    aula: settings.aula,
    grupo: settings.grupo,
    turno: settings.turno,
    especialidad: settings.especialidad,
  });
  const [confirmando, setConfirmando] = useState(false);
  const [guardado, setGuardado] = useState(false);
  const [bandeja, setBandeja] = useState(leerCerrarABandeja);

  const set = (campo: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setGuardado(false);
    setForm((f) => ({ ...f, [campo]: e.target.value }));
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const { password, ...resto } = form;
    await guardar.mutateAsync({ ...resto, ...(password ? { password } : {}) });
    setForm((f) => ({ ...f, password: "" }));
    setGuardado(true);
  }

  const incompleto =
    !form.cuenta || !form.nombre || !form.matricula || (!settings.tiene_password && !form.password);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-8">
      <PageHeader titulo="Configuración" descripcion="Tus datos de acceso y preferencias." />

      <form onSubmit={onSubmit} className="space-y-4 rounded-xl border bg-card p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Cuenta SIASE</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="cuenta">Cuenta</Label>
            <Input id="cuenta" autoComplete="username" value={form.cuenta} onChange={set("cuenta")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Contraseña</Label>
            <PasswordInput
              id="password"
              value={form.password}
              onChange={(v) => {
                setGuardado(false);
                setForm((f) => ({ ...f, password: v }));
              }}
              placeholder={settings.tiene_password ? "Guardada (escribe para cambiarla)" : undefined}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="nombre">Nombre completo</Label>
            <Input id="nombre" value={form.nombre} onChange={set("nombre")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="matricula">Matrícula</Label>
            <Input id="matricula" value={form.matricula} onChange={set("matricula")} />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          La contraseña se guarda en el Administrador de credenciales de Windows, nunca en archivos.
        </p>
      <div className="space-y-4 border-t pt-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Datos de la portada
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="aula">Aula</Label>
            <Input id="aula" value={form.aula} onChange={set("aula")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="grupo">Grupo</Label>
            <Input id="grupo" value={form.grupo} onChange={set("grupo")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="turno">Turno</Label>
            <Input id="turno" value={form.turno} onChange={set("turno")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="especialidad">Especialidad</Label>
            <Input id="especialidad" value={form.especialidad} onChange={set("especialidad")} />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Se usan para rellenar solas todas las portadas. La fecha siempre es la de hoy.
        </p>
      </div>
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={incompleto || guardar.isPending}>
            <Save /> Guardar
          </Button>
          {guardado && <span className="text-sm text-success">Cambios guardados</span>}
          {guardar.error && <span className="text-sm text-destructive">{guardar.error.message}</span>}
        </div>
      </form>

      <section className="space-y-4 rounded-xl border bg-card p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Gemini</h2>
        <p className="text-sm text-muted-foreground">
          Se abre Chrome para que inicies sesión tú mismo en Gemini. La sesión queda guardada en el perfil
          local.
        </p>
        <Button variant="secondary" onClick={() => gemini.start(api.loginGemini)} disabled={gemini.running}>
          <LogIn /> Iniciar sesión en Gemini
        </Button>
        <JobProgress job={gemini.job} error={gemini.error} onCambio={gemini.actualizar} />
      </section>

      <section className="space-y-5 rounded-xl border bg-card p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Preferencias</h2>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium">Tema</p>
            <p className="text-xs text-muted-foreground">«Sistema» sigue el tema de Windows.</p>
          </div>
          <ThemeSelector />
        </div>
        <Preferencia
          id="bandeja"
          titulo="Minimizar a la bandeja al cerrar"
          descripcion="Al cerrar la ventana la aplicación sigue en la bandeja del sistema. Para salir usa su menú."
          checked={bandeja}
          onChange={(v) => {
            setBandeja(v);
            void aplicarCerrarABandeja(v);
          }}
        />
        <Preferencia
          id="dev"
          titulo="Modo DEV"
          descripcion="Muestra el navegador mientras trabaja la automatización."
          checked={settings.dev}
          onChange={(v) => guardar.mutate({ dev: v })}
        />
        <Preferencia
          id="reducir"
          titulo="Reducir animaciones"
          descripcion="Desactiva el fondo animado y los efectos de movimiento."
          checked={settings.reducir_animaciones}
          onChange={(v) => guardar.mutate({ reducir_animaciones: v })}
        />
        <div className="space-y-3">
          <Preferencia
            id="sin-revisar"
            titulo="Entregar sin revisar"
            descripcion="Omite la revisión antes de subir el PDF a NEXUS. Úsalo con mucho cuidado."
            checked={settings.entregar_sin_revisar || confirmando}
            onChange={(v) => {
              if (v) setConfirmando(true);
              else {
                setConfirmando(false);
                guardar.mutate({ entregar_sin_revisar: false });
              }
            }}
          />
          {confirmando && !settings.entregar_sin_revisar && (
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3">
              <ShieldAlert className="size-5 text-destructive" />
              <p className="flex-1 text-sm">
                Las tareas se entregarán en NEXUS sin que las revises. Mantén presionado para confirmar.
              </p>
              <HoldButton
                onComplete={() => {
                  guardar.mutate({ entregar_sin_revisar: true });
                  setConfirmando(false);
                }}
              >
                Mantén para activar
              </HoldButton>
              <Button variant="ghost" size="sm" onClick={() => setConfirmando(false)}>
                Cancelar
              </Button>
            </div>
          )}
        </div>
      </section>
      <ConfigAvanzada settings={settings} />
    </div>
  );
}

function Preferencia({
  id,
  titulo,
  descripcion,
  checked,
  onChange,
}: {
  id: string;
  titulo: string;
  descripcion: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <Label htmlFor={id} className="text-sm">
          {titulo}
        </Label>
        <p className="text-xs text-muted-foreground">{descripcion}</p>
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
