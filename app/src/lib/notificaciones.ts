import type { Alerta } from "@/lib/api";

const CLAVE = "nmwfm.alertas";

export function hoyClave(ahora = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${ahora.getFullYear()}-${p(ahora.getMonth() + 1)}-${p(ahora.getDate())}`;
}

export function pendientesDeAvisar(alertas: Alerta[], ahora = new Date()): Alerta[] {
  let vistas: string[] = [];
  try {
    const guardado = JSON.parse(localStorage.getItem(CLAVE) ?? "null") as {
      fecha: string;
      ids: string[];
    } | null;
    if (guardado?.fecha === hoyClave(ahora)) vistas = guardado.ids;
  } catch {
    vistas = [];
  }
  return alertas.filter((a) => !vistas.includes(`${a.tarea_id}:${a.cuando}`));
}

export function marcarAvisadas(alertas: Alerta[], ahora = new Date()) {
  try {
    const previas = pendientesDeAvisar([], ahora);
    void previas;
    const actual = JSON.parse(localStorage.getItem(CLAVE) ?? "null") as {
      fecha: string;
      ids: string[];
    } | null;
    const base = actual?.fecha === hoyClave(ahora) ? actual.ids : [];
    const ids = [...new Set([...base, ...alertas.map((a) => `${a.tarea_id}:${a.cuando}`)])];
    localStorage.setItem(CLAVE, JSON.stringify({ fecha: hoyClave(ahora), ids }));
  } catch {
    return;
  }
}

export function resumenAlertas(alertas: Alerta[]): { titulo: string; cuerpo: string } {
  const hoy = alertas.filter((a) => a.cuando === "hoy");
  const manana = alertas.filter((a) => a.cuando === "manana");
  const partes: string[] = [];
  if (hoy.length) partes.push(`${hoy.length} ${hoy.length === 1 ? "vence" : "vencen"} hoy`);
  if (manana.length) partes.push(`${manana.length} ${manana.length === 1 ? "vence" : "vencen"} mañana`);
  return {
    titulo: `Tareas por entregar: ${partes.join(" y ")}`,
    cuerpo: alertas
      .slice(0, 4)
      .map((a) => `${a.titulo} (${a.materia_nombre})`)
      .join("\n"),
  };
}

export async function notificar(titulo: string, cuerpo: string): Promise<boolean> {
  try {
    if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
      const n = await import("@tauri-apps/plugin-notification");
      let permitido = await n.isPermissionGranted();
      if (!permitido) permitido = (await n.requestPermission()) === "granted";
      if (!permitido) return false;
      n.sendNotification({ title: titulo, body: cuerpo });
      return true;
    }
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      new Notification(titulo, { body: cuerpo });
      return true;
    }
  } catch {
    return false;
  }
  return false;
}
