import { configureApi, configureSocket, type BackendInfo } from "@/lib/api";

export const isMock = import.meta.env.VITE_MOCK === "1";

function inTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function initBackend(): Promise<void> {
  if (isMock) {
    const { createMockBackend } = await import("@/mock/backend");
    const mock = createMockBackend();
    configureApi({ transport: mock.transport, token: "dev" });
    configureSocket(mock.createSocket);
    return;
  }
  if (!inTauri()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  const info = await invoke<BackendInfo>("backend_info");
  configureApi({ base: `http://127.0.0.1:${info.port}`, token: info.token });
}
