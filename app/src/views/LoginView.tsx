import { useState, type FormEvent } from "react";
import { Loader2, RefreshCw, Rocket, Send, Sparkles } from "lucide-react";
import { Logo } from "@/components/Logo";
import { PasswordInput } from "@/components/PasswordInput";
import RotatingText from "@/components/RotatingText";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type Settings } from "@/lib/api";
import { useReducedMotion } from "@/lib/app-context";
import { useJobRunner, useSaveSettings } from "@/lib/queries";
import { guardarRecordar, leerRecordar } from "@/lib/session";

const FRASES = [
  "Tus tareas, en piloto automático",
  "De NEXUS a entregado en minutos",
  "Tú revisas, nosotros hacemos el resto",
];

const PUNTOS = [
  { icono: RefreshCw, texto: "Sincroniza NEXUS" },
  { icono: Sparkles, texto: "Genera con Gemini" },
  { icono: Send, texto: "Entrega con un clic" },
];

export function LoginView({ settings, onEntrar }: { settings: Settings; onEntrar: () => void }) {
  const reducido = useReducedMotion();
  const guardar = useSaveSettings();
  const [form, setForm] = useState({
    cuenta: settings.cuenta,
    password: "",
    nombre: settings.nombre,
    matricula: settings.matricula,
  });
  const [recordar, setRecordar] = useState(leerRecordar);
  const [fallo, setFallo] = useState<string | null>(null);

  const verificacion = useJobRunner((j) => {
    if (j.estado === "ok") finalizar();
    else setFallo(j.mensaje ?? "No se pudo verificar la cuenta en SIASE");
  });

  const set = (campo: "cuenta" | "nombre" | "matricula") => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [campo]: e.target.value }));

  const completo =
    !!form.cuenta.trim() &&
    !!form.nombre.trim() &&
    !!form.matricula.trim() &&
    (settings.tiene_password || !!form.password);
  const ocupado = guardar.isPending || verificacion.running;

  function finalizar() {
    guardarRecordar(recordar);
    onEntrar();
  }

  async function persistir(): Promise<boolean> {
    setFallo(null);
    const { password, ...resto } = form;
    try {
      await guardar.mutateAsync({ ...resto, ...(password ? { password } : {}) });
      return true;
    } catch (e) {
      setFallo(e instanceof Error ? e.message : "No se pudieron guardar los datos");
      return false;
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!completo || ocupado) return;
    if (await persistir()) await verificacion.start(api.validarSiase);
  }

  async function sinVerificar() {
    if (!completo || ocupado) return;
    if (await persistir()) finalizar();
  }

  const mensajeError = fallo ?? verificacion.error;

  return (
    <div className="grid min-h-full overflow-y-auto lg:grid-cols-[55fr_45fr]">
      <section className="relative flex flex-col justify-center gap-8 px-8 py-12 lg:px-16">
        <div className="flex items-center gap-3">
          <Logo className="size-12" />
          <span className="text-brand text-3xl font-bold tracking-tight">nmwfm</span>
        </div>
        <div className="min-h-[7.5rem] max-w-xl text-4xl font-semibold leading-tight tracking-tight lg:text-5xl">
          {reducido ? (
            <span>{FRASES[0]}</span>
          ) : (
            <RotatingText
              texts={FRASES}
              rotationInterval={3200}
              splitBy="words"
              staggerDuration={0}
              animatePresenceMode="wait"
              mainClassName="flex-wrap"
              splitLevelClassName="overflow-hidden pb-1"
              elementLevelClassName="mr-[0.25em]"
            />
          )}
        </div>
        <ul className="space-y-3">
          {PUNTOS.map(({ icono: Icono, texto }) => (
            <li key={texto} className="flex items-center gap-3 text-base text-muted-foreground">
              <span className="flex size-9 items-center justify-center rounded-lg bg-accent text-primary">
                <Icono className="size-5" />
              </span>
              {texto}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <form
          onSubmit={onSubmit}
          aria-labelledby="titulo-login"
          className="w-full max-w-md space-y-5 rounded-2xl border bg-card p-8 shadow-pop"
        >
          <div className="space-y-1">
            <h1 id="titulo-login" className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              Iniciar sesión
              <Rocket className="size-5 text-mint" />
            </h1>
            <p className="text-sm text-muted-foreground">Usa tu cuenta de SIASE para continuar.</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="cuenta">Cuenta</Label>
            <Input id="cuenta" autoComplete="username" value={form.cuenta} onChange={set("cuenta")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Contraseña</Label>
            <PasswordInput
              id="password"
              value={form.password}
              onChange={(v) => setForm((f) => ({ ...f, password: v }))}
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

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={recordar}
              onChange={(e) => setRecordar(e.target.checked)}
              className="size-4 accent-primary"
            />
            Recordarme
          </label>

          {mensajeError && (
            <p
              role="alert"
              className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
            >
              {mensajeError}
            </p>
          )}

          <Button type="submit" size="lg" className="w-full" disabled={!completo || ocupado}>
            {ocupado ? (
              <>
                <Loader2 className="animate-spin" /> Verificando con SIASE...
              </>
            ) : (
              "Entrar"
            )}
          </Button>
          <button
            type="button"
            onClick={sinVerificar}
            disabled={!completo || ocupado}
            className="block w-full text-center text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline disabled:pointer-events-none disabled:opacity-50"
          >
            Continuar sin verificar
          </button>
        </form>
      </section>
    </div>
  );
}
