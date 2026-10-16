import { act, cleanup, renderHook, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, configureApi, configureSocket } from "@/lib/api";
import { NavProvider } from "@/lib/app-context";
import { useSyncPeriodico } from "@/lib/sync";
import { createMockBackend } from "@/mock/backend";
import { ConfigView } from "@/views/ConfigView";

describe("configuración avanzada", () => {
  beforeEach(async () => {
    const mock = createMockBackend({ stepMs: 2 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <NavProvider initial={{ name: "config" }}>
          <ConfigView />
        </NavProvider>
      </QueryClientProvider>,
    );
  }

  it("guarda el intervalo de sincronización automática", async () => {
    const user = userEvent.setup();
    montar();
    const select = await screen.findByLabelText("Sincronizar automáticamente cada N horas");
    await user.selectOptions(select, "4");
    await waitFor(async () => expect((await api.getSettings()).sync_cada_horas).toBe(4));
  });

  it("crea un respaldo y lo restaura tras confirmar", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: "Crear respaldo" }));
    const lista = await screen.findByRole("list", { name: "Respaldos" });
    expect(lista).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Restaurar/ }));
    await user.click(await screen.findByRole("button", { name: "Sí, restaurar" }));
    expect(await screen.findByText(/Respaldo restaurado/)).toBeInTheDocument();
  });

  it("ejecuta el diagnóstico y muestra el reporte con los fallos", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: "Ejecutar diagnóstico" }));
    const reporte = await screen.findByRole("list", { name: "Reporte de diagnóstico" }, { timeout: 5000 });
    expect(reporte).toHaveTextContent("Lista de materias");
    expect(reporte).toHaveTextContent("selector desactualizado");
  }, 15000);

  it("el temporizador lanza la sincronización cada N horas", () => {
    vi.useFakeTimers();
    const ejecutar = vi.fn();
    renderHook(() => useSyncPeriodico(2, ejecutar));
    act(() => vi.advanceTimersByTime(2 * 3_600_000));
    expect(ejecutar).toHaveBeenCalledTimes(1);
    act(() => vi.advanceTimersByTime(2 * 3_600_000));
    expect(ejecutar).toHaveBeenCalledTimes(2);
  });

  it("no programa nada si está desactivado", () => {
    vi.useFakeTimers();
    const ejecutar = vi.fn();
    renderHook(() => useSyncPeriodico(0, ejecutar));
    act(() => vi.advanceTimersByTime(48 * 3_600_000));
    expect(ejecutar).not.toHaveBeenCalled();
  });

  it("muestra el estado de Ollama y guarda el modelo del asistente", async () => {
    const user = userEvent.setup();
    montar();
    const estado = await screen.findByRole("status", { name: "Estado de Ollama" });
    expect(await within(estado).findByText(/Ollama: conectado/)).toBeInTheDocument();
    const campo = screen.getByLabelText("Modelo del asistente (Ollama)");
    expect(campo).toHaveValue("qwen3:4b");
    await user.clear(campo);
    await user.type(campo, "qwen3:8b");
    await user.tab();
    await waitFor(async () => expect((await api.getSettings()).asistente_modelo).toBe("qwen3:8b"));
    expect(await within(estado).findByText(/Modelo qwen3:8b: instalado/)).toBeInTheDocument();
  });

  it("explica cómo instalar Ollama cuando no está disponible", async () => {
    const sinOllama = createMockBackend({ stepMs: 2, asistenteDisponible: false });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: sinOllama.transport });
    configureSocket(sinOllama.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
    montar();
    const estado = await screen.findByRole("status", { name: "Estado de Ollama" });
    expect(await within(estado).findByText(/Ollama: no encontrado/)).toBeInTheDocument();
    expect(await screen.findByText(/ollama pull qwen3:4b/)).toBeInTheDocument();
  });
});
