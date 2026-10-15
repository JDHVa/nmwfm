import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";
import { EntregarStep } from "@/views/tarea/EntregarStep";
import { NavProvider } from "@/lib/app-context";

afterEach(() => cleanup());

describe("reentrega", () => {
  it("avisa que se reemplaza la entrega anterior y muestra el mensaje de NEXUS", async () => {
    const mock = createMockBackend({ stepMs: 5 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    const tarea = mock.etapas["m1"][0].tareas[0];
    await api.subirImagenes(tarea.id, [new File(["x"], "p.png", { type: "image/png" })]);
    const job = await api.generar(tarea.id);
    await waitFor(async () => expect((await api.job(job.id)).estado).toBe("ok"));
    await api.entregar(tarea.id);
    await waitFor(() => expect(tarea.estado).toBe("entregada"));
    const detalle = await api.tarea(tarea.id);

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <NavProvider initial={{ name: "materias" }}>
          <EntregarStep tarea={detalle} onAtras={() => {}} />
        </NavProvider>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();
    const boton = await screen.findByRole("button", { name: "Reemplazar entrega" });
    await waitFor(() => expect(boton).toBeEnabled());
    await user.click(boton);
    expect(
      await screen.findByText("Ya entregaste esta tarea. Se reemplazará la entrega anterior."),
    ).toBeInTheDocument();
    const botones = screen.getAllByRole("button", { name: "Reemplazar entrega" });
    await user.click(botones[botones.length - 1]);
    expect(
      (await screen.findAllByText("La Tarea ha sido cargada y entregada con éxito", {}, { timeout: 5000 }))
        .length,
    ).toBeGreaterThan(0);
  }, 15000);
});
