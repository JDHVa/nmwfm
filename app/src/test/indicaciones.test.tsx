import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

describe("indicaciones del profesor", () => {
  beforeEach(async () => {
    localStorage.clear();
    const mock = createMockBackend({ stepMs: 4 });
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

  async function abrirTarea(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByText("Algoritmos Bio Inspirados"));
    await user.click(await screen.findByText("Dimensión 2 - Comprensión - Ficha Técnica"));
  }

  it("se editan y guardan con el aviso de prioridad, y se ven también en Generar", async () => {
    const user = userEvent.setup();
    montar();
    await abrirTarea(user);
    expect(await screen.findByText(/Tienen prioridad sobre la descripción de NEXUS/)).toBeInTheDocument();
    const area = screen.getByLabelText("Indicaciones del profesor");
    const guardar = screen.getByRole("button", { name: "Guardar indicaciones" });
    expect(guardar).toBeDisabled();
    await user.type(area, "Es en equipo de 3");
    await user.click(guardar);
    expect(await screen.findByText("Guardadas")).toBeInTheDocument();
    expect((await api.tarea("m1-t12")).indicaciones).toBe("Es en equipo de 3");
  });

  it("aparecen en el paso Generar con el texto guardado", async () => {
    await api.indicaciones("m1-t12", "Máximo 2 páginas");
    await api.subirImagenes("m1-t12", [new File(["x"], "p.png", { type: "image/png" })]);
    const user = userEvent.setup();
    montar();
    await abrirTarea(user);
    expect(await screen.findByLabelText("Indicaciones del profesor")).toHaveValue("Máximo 2 páginas");
    await user.click(await screen.findByRole("button", { name: "Continuar a generar" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Indicaciones del profesor")).toHaveValue("Máximo 2 páginas"),
    );
    expect(screen.getByRole("button", { name: /Generar tarea/ })).toBeInTheDocument();
  });
});
