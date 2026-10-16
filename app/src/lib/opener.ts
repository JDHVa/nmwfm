export const URL_NEXUS = "https://plataformanexus.uanl.mx/";

export function enTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function abrirEnNavegador(url: string): Promise<void> {
  if (enTauri()) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

export function alPulsarEnlace(e: { preventDefault: () => void }, href: string | undefined) {
  if (!href || !enTauri()) return;
  e.preventDefault();
  void abrirEnNavegador(href);
}
