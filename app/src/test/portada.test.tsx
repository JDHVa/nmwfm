import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, configureApi, configureSocket } from "@/lib/api";
import { NavProvider } from "@/lib/app-context";
import { createMockBackend } from "@/mock/backend";
import { GenerarStep } from "@/views/tarea/GenerarStep";

const runner = {
  job: null,
  error: null,
  running: false,
  reset: () => {},
  start: vi.fn(async (launch: () => Promise<unknown>) => {
    await launch();
    return null;
  }),
} as unknown as Parameters<typeof GenerarStep>[0]["runner"];

describe("portada en el paso Generar", () => {
  beforeEach(async () => {
    const mock = createMockBackend({ stepMs: 5 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana López", matricula: "1234", password: "x" });
    await api.subirImagenes("m1-t12", [new File(["x"], "p.png", { type: "image/png" })]);
  });
  afterEach(() => cleanup());

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <NavProvider initial={{ name: "materias" }}>
          <GenerarStep
            tareaId="m1-t12"
            materiaId="m1"
            runner={runner}
            onAtras={() => {}}
            onListo={() => {}}
          />
        </NavProvider>
      </QueryClientProvider>,
    );
  }

  const contenido = (img: HTMLElement) => decodeURIComponent((img as HTMLImageElement).src);

  it("muestra la vista previa con el profesor de la materia y permite editarla", async () => {
    const user = userEvent.setup();
    montar();
    const img = await screen.findByAltText("Vista previa de la portada");
    expect(contenido(img)).toContain("CAVAZOS");
    const profesor = screen.getByLabelText("Profesor");
    await waitFor(() => expect(profesor).toHaveValue("CAVAZOS MARTÍNEZ RAFAEL ALFREDO"));
    await user.clear(profesor);
    await user.type(profesor, "DRA. PÉREZ");
    await waitFor(
      () => expect(contenido(screen.getByAltText("Vista previa de la portada"))).toContain("DRA. PÉREZ"),
      {
        timeout: 3000,
      },
    );
  });

  it("envía el profesor y el título editados al generar", async () => {
    const generar = vi.spyOn(api, "generar");
    const user = userEvent.setup();
    montar();
    await waitFor(() => expect(screen.getByLabelText("Título")).not.toHaveValue(""));
    const titulo = screen.getByLabelText("Título");
    await user.clear(titulo);
    await user.type(titulo, "Mi ficha");
    await user.click(screen.getByRole("button", { name: /Generar tarea/ }));
    await waitFor(() => expect(generar).toHaveBeenCalled());
    expect(generar.mock.calls[0][2]).toEqual({ titulo: "Mi ficha" });
  });
});
