import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

function montar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

async function configurar(stepMs: number) {
  localStorage.clear();
  const mock = createMockBackend({ stepMs });
  configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
  configureSocket(mock.createSocket);
  await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
}

describe("sync automático", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => cleanup());

  it("al entrar lanza el sync y muestra el overlay de primera vez, que se minimiza", async () => {
    await configurar(80);
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    expect(await screen.findByText("Preparando todo por primera vez")).toBeInTheDocument();
    expect(screen.getByText(/solo se hace una vez/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Seguir en segundo plano" }));
    expect(screen.queryByText("Preparando todo por primera vez")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sincronizando/ })).toBeInTheDocument();
  });

  it("termina, marca la sincronización inicial y deja el indicador al día", async () => {
    await configurar(5);
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    expect(await screen.findByRole("button", { name: /Al día/ }, { timeout: 8000 })).toBeInTheDocument();
    expect((await api.getSettings()).sync_inicial_hecha).toBe(true);
    expect(screen.queryByText("Preparando todo por primera vez")).not.toBeInTheDocument();
  }, 15000);

  it("si la sincronización inicial ya se hizo no muestra el overlay", async () => {
    await configurar(5);
    const job = await api.sync("completo");
    await waitFor(async () => expect((await api.job(job.id)).estado).toBe("ok"));
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    expect(await screen.findByRole("heading", { name: "Materias" })).toBeInTheDocument();
    expect(screen.queryByText("Preparando todo por primera vez")).not.toBeInTheDocument();
  });

  it("ofrece sincronizar todo de nuevo", async () => {
    await configurar(5);
    const job = await api.sync("completo");
    await waitFor(async () => expect((await api.job(job.id)).estado).toBe("ok"));
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    const mas = await screen.findByRole("button", { name: "Más opciones de sincronización" });
    await waitFor(() => expect(mas).toBeEnabled());
    await user.click(mas);
    expect(await screen.findByRole("button", { name: "Sincronizar todo de nuevo" })).toBeInTheDocument();
  });

  it("no sincroniza al abrir cuando la sincronización inicial ya se hizo", async () => {
    await configurar(5);
    const job = await api.sync("completo");
    await waitFor(async () => expect((await api.job(job.id)).estado).toBe("ok"));
    const espia = vi.spyOn(api, "sync");
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    expect(await screen.findByRole("button", { name: /Al día/ })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 300));
    expect(espia).not.toHaveBeenCalled();
    espia.mockRestore();
  });
});
