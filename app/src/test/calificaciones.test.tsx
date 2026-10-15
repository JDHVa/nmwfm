import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { configureApi, configureSocket } from "@/lib/api";
import { NavProvider } from "@/lib/app-context";
import { createMockBackend } from "@/mock/backend";
import { MateriaView } from "@/views/MateriaView";

describe("calificaciones de la materia", () => {
  beforeEach(() => {
    const mock = createMockBackend({ stepMs: 2 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
  });
  afterEach(() => cleanup());

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <NavProvider initial={{ name: "materia", id: "m1" }}>
          <MateriaView id="m1" />
        </NavProvider>
      </QueryClientProvider>,
    );
  }

  it("muestra la pestaña con las calificaciones y el promedio", async () => {
    const user = userEvent.setup();
    montar();
    expect(await screen.findByText("Etapa 1: Algoritmos Evolutivos")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Calificaciones" }));
    expect(await screen.findByLabelText("Promedio")).toHaveTextContent("9.2");
    expect(screen.getByText("Dimensión 2 - Comprensión - Ficha Técnica")).toBeInTheDocument();
    expect(screen.getAllByText("Sin calificar").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("tab", { name: "Tareas" }));
    expect(await screen.findByText("Etapa 1: Algoritmos Evolutivos")).toBeInTheDocument();
  });
});
