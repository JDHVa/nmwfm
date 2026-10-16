import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import * as notificaciones from "@/lib/notificaciones";
import { createMockBackend } from "@/mock/backend";

describe("novedades y alertas", () => {
  beforeEach(async () => {
    localStorage.clear();
    const mock = createMockBackend({ stepMs: 5 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
  }

  it("la campanita cuenta las novedades sin leer y permite marcarlas como leídas", async () => {
    vi.spyOn(notificaciones, "notificar").mockResolvedValue(false);
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    const campana = await screen.findByRole("button", { name: "Novedades: 3 sin leer" });
    await user.click(campana);
    expect(
      await screen.findByText("Tarea nueva · Algoritmos Bio Inspirados", { exact: false }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Marcar todas como leídas/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Novedades" })).toBeInTheDocument());
    expect((await api.novedades()).every((n) => n.leida)).toBe(true);
  });

  it("avisa una sola vez al día de las tareas que vencen hoy o mañana", async () => {
    const enviar = vi.spyOn(notificaciones, "notificar").mockResolvedValue(true);
    const user = userEvent.setup();
    const { unmount } = montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await waitFor(() => expect(enviar).toHaveBeenCalledTimes(1));
    expect(enviar.mock.calls[0][0]).toMatch(/vencen? hoy/);
    unmount();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await screen.findByRole("heading", { name: "Materias" });
    await new Promise((r) => setTimeout(r, 300));
    expect(enviar).toHaveBeenCalledTimes(1);
  });

  it("agrupa las alertas en un resumen", () => {
    const r = notificaciones.resumenAlertas([
      { tarea_id: "1", materia_id: "m", materia_nombre: "Lógica", titulo: "A", hasta: "", cuando: "hoy" },
      { tarea_id: "2", materia_id: "m", materia_nombre: "Lógica", titulo: "B", hasta: "", cuando: "manana" },
    ]);
    expect(r.titulo).toBe("Tareas por entregar: 1 vence hoy y 1 vence mañana");
  });
});
