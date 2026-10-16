import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

const abrir = vi.hoisted(() => vi.fn());
vi.mock("@/lib/opener", () => ({ URL_NEXUS: "https://plataformanexus.uanl.mx/", abrirEnNavegador: abrir }));

describe("exámenes y PIA", () => {
  beforeEach(async () => {
    localStorage.clear();
    abrir.mockReset();
    const mock = createMockBackend({ stepMs: 5 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  });
  afterEach(() => cleanup());

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
  }

  it("muestra el examen como recordatorio sin Stepper y abre NEXUS", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByText("Algoritmos Bio Inspirados"));
    expect((await screen.findAllByText("Examen en NEXUS")).length).toBeGreaterThan(0);
    await user.click(await screen.findByText("Examen Etapa 1"));
    expect(await screen.findByText("Este examen se contesta directamente en NEXUS")).toBeInTheDocument();
    expect(screen.queryByText("Insumos")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Elegir archivos" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Abrir NEXUS" }));
    expect(abrir).toHaveBeenCalledWith("https://plataformanexus.uanl.mx/");
  });

  it("incluye exámenes y PIA con su badge en Próximas entregas", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByRole("button", { name: "Próximas entregas" }));
    await screen.findByRole("heading", { name: "Próximas entregas" });
    expect((await screen.findAllByText("Examen en NEXUS")).length).toBeGreaterThan(0);
    const filas = await screen.findAllByRole("button", { name: /PIA - Informe/ });
    expect(within(filas[0]).getAllByText("PIA").length).toBe(2);
  });

  it("el PIA usa el mismo flujo que una evidencia", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByRole("button", { name: "Próximas entregas" }));
    const filas = await screen.findAllByRole("button", { name: /PIA - Informe/ });
    await user.click(filas[0]);
    expect(await screen.findByRole("button", { name: "Elegir archivos" })).toBeInTheDocument();
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });
});
