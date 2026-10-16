import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

const captura = vi.hoisted(() => ({ alPedir: null as null | (() => void) }));

vi.mock("@/lib/bandeja", async (original) => {
  const real = await original<typeof import("@/lib/bandeja")>();
  return {
    ...real,
    sincronizarPreferenciaConRust: async () => {},
    escucharSyncDeBandeja: async (cb: () => void) => {
      captura.alPedir = cb;
      return () => {
        captura.alPedir = null;
      };
    },
  };
});

describe("bandeja del sistema", () => {
  beforeEach(async () => {
    localStorage.clear();
    captura.alPedir = null;
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

  it("«Sincronizar ahora» del menú de la bandeja lanza una sincronización", async () => {
    const sync = vi.spyOn(api, "sync");
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await waitFor(() => expect(captura.alPedir).not.toBeNull());
    await waitFor(() => expect(sync).toHaveBeenCalledTimes(1));
    await waitFor(async () => expect((await api.getSettings()).sync_inicial_hecha).toBe(true), {
      timeout: 20000,
    });
    captura.alPedir!();
    await waitFor(() => expect(sync).toHaveBeenCalledWith("incremental"));
  });

  it("la preferencia de cerrar a la bandeja se guarda y viene activa por defecto", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByRole("button", { name: "Configuración" }));
    const interruptor = await screen.findByRole("switch", { name: "Minimizar a la bandeja al cerrar" });
    expect(interruptor).toBeChecked();
    await user.click(interruptor);
    await waitFor(() => expect(interruptor).not.toBeChecked());
    expect(localStorage.getItem("nmwfm.bandeja")).toBe("0");
  });
});
