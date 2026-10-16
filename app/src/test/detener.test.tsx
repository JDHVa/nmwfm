import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { JobProgress } from "@/components/JobProgress";
import { api, configureApi, configureSocket, jobCancelado, type Job } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";
import { EntregarStep } from "@/views/tarea/EntregarStep";
import { NavProvider } from "@/lib/app-context";

afterEach(() => cleanup());

function Arnes({ lanzar }: { lanzar: () => Promise<Job> }) {
  const [job, setJob] = useState<Job | null>(null);
  return (
    <>
      <button onClick={async () => setJob(await lanzar())}>lanzar</button>
      <JobProgress job={job} onCambio={setJob} />
    </>
  );
}

async function preparar() {
  const mock = createMockBackend({ stepMs: 400 });
  configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
  configureSocket(mock.createSocket);
  await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  return mock;
}

describe("detener jobs", () => {
  it("el mock cancela un job y lo marca como cancelado", async () => {
    await preparar();
    const job = await api.sync("auto");
    const cancelado = await api.cancelarJob(job.id);
    expect(cancelado.estado).toBe("error");
    expect(cancelado.mensaje).toBe("Cancelado por el usuario");
    expect(jobCancelado(cancelado)).toBe(true);
    await new Promise((r) => setTimeout(r, 200));
    expect((await api.job(job.id)).estado).toBe("error");
  });

  it("muestra Detener mientras corre y el mensaje sin alarma al cancelar", async () => {
    await preparar();
    render(<Arnes lanzar={() => api.sync("auto")} />);
    const user = userEvent.setup();
    expect(screen.queryByRole("button", { name: /Detener/ })).toBeNull();
    await user.click(screen.getByText("lanzar"));
    await user.click(await screen.findByRole("button", { name: /Detener/ }));
    expect(await screen.findByText("Cancelado por el usuario")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Detener/ })).toBeNull();
    expect(document.querySelector(".text-destructive")).toBeNull();
  });

  it("pide confirmación con un diálogo antes de detener una entrega", async () => {
    const mock = await preparar();
    const tarea = mock.etapas["m1"][0].tareas[0];
    await api.subirImagenes(tarea.id, [new File(["x"], "p.png", { type: "image/png" })]);
    const gen = await api.generar(tarea.id);
    await waitFor(async () => expect((await api.job(gen.id)).estado).toBe("ok"), { timeout: 20000 });
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
    const entregar = await screen.findByRole("button", { name: "Entregar" });
    await waitFor(() => expect(entregar).toBeEnabled());
    await user.click(entregar);
    await user.click(await screen.findByRole("button", { name: "Sí, entregar" }));
    await user.click(await screen.findByRole("button", { name: /^Detener/ }));
    expect(await screen.findByText("¿Detener la entrega?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sí, detener" }));
    expect((await screen.findAllByText("Cancelado por el usuario")).length).toBeGreaterThan(0);
    expect(tarea.estado).not.toBe("entregada");
  }, 40000);
});
