const CLAVE = "nmwfm.bandeja";

function enTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function leerCerrarABandeja(): boolean {
  try {
    return localStorage.getItem(CLAVE) !== "0";
  } catch {
    return true;
  }
}

export async function aplicarCerrarABandeja(valor: boolean): Promise<void> {
  try {
    localStorage.setItem(CLAVE, valor ? "1" : "0");
  } catch {
    return;
  }
  if (!enTauri()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("set_cerrar_a_bandeja", { valor });
}

export async function sincronizarPreferenciaConRust(): Promise<void> {
  if (!enTauri()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("set_cerrar_a_bandeja", { valor: leerCerrarABandeja() });
}

export async function escucharSyncDeBandeja(alPedir: () => void): Promise<() => void> {
  if (!enTauri()) return () => {};
  const { listen } = await import("@tauri-apps/api/event");
  return listen("tray-sync", alPedir);
}
