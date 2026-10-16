import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, configureApi, configureSocket } from "@/lib/api";
import { NavProvider } from "@/lib/app-context";
import { createMockBackend } from "@/mock/backend";
import { ConfigView } from "@/views/ConfigView";
import { GenerarStep } from "@/views/tarea/GenerarStep";

vi.mock("@/views/tarea/PdfPreview", () => ({
  default: ({ url }: { url: string }) => <div>{url}</div>,
}));

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

function envolver(hijo: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NavProvider initial={{ name: "config" }}>{hijo}</NavProvider>
    </QueryClientProvider>,
  );
}

describe("instrucciones fijas del prompt", () => {
  beforeEach(async () => {
    const mock = createMockBackend({ stepMs: 2 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  });
  afterEach(() => cleanup());

  it("desactiva una instrucción y la guarda", async () => {
    const user = userEvent.setup();
    envolver(<ConfigView />);
    const fila = await screen.findByTestId("instruccion-referencias_apa7");
    await user.click(within(fila).getByRole("switch"));
    await waitFor(async () => {
      const lista = (await api.getSettings()).instrucciones_fijas ?? [];
      expect(lista.find((i) => i.id === "referencias_apa7")?.activa).toBe(false);
    });
  });

  it("agrega y borra una instrucción propia, y no deja borrar las de sistema", async () => {
    const user = userEvent.setup();
    envolver(<ConfigView />);
    const fila = await screen.findByTestId("instruccion-referencias_apa7");
    expect(within(fila).queryByRole("button", { name: "Borrar" })).toBeNull();
    await user.type(screen.getByLabelText("Agregar instrucción"), "Incluye un ejemplo");
    await user.click(screen.getByRole("button", { name: /^Agregar$/ }));
    const propia = await screen.findByText("Incluye un ejemplo");
    const nueva = (await api.getSettings()).instrucciones_fijas!.at(-1)!;
    expect(nueva.id).toMatch(/^u-/);
    expect(nueva.sistema).toBe(false);
    await user.click(within(propia.closest("li")!).getByRole("button", { name: "Borrar" }));
    await waitFor(() => expect(screen.queryByText("Incluye un ejemplo")).toBeNull());
  });

  it("edita el texto y reordena", async () => {
    const user = userEvent.setup();
    envolver(<ConfigView />);
    const fila = await screen.findByTestId("instruccion-rubrica_maxima");
    await user.click(within(fila).getByRole("button", { name: "Editar" }));
    const caja = within(fila).getByLabelText("Texto de la instrucción");
    await user.clear(caja);
    await user.type(caja, "Texto nuevo");
    await user.click(within(fila).getByRole("button", { name: /Guardar texto/ }));
    await waitFor(async () =>
      expect((await api.getSettings()).instrucciones_fijas![0].texto).toBe("Texto nuevo"),
    );
    const bajar = within(screen.getByTestId("instruccion-rubrica_maxima")).getByRole("button", {
      name: "Bajar",
    });
    await user.click(bajar);
    await waitFor(async () =>
      expect((await api.getSettings()).instrucciones_fijas![1].id).toBe("rubrica_maxima"),
    );
  });

  it("restaura las predeterminadas y limita la espera a 0-15", async () => {
    const user = userEvent.setup();
    envolver(<ConfigView />);
    const campo = await screen.findByLabelText(/Espera antes de enviar a Gemini/);
    await user.clear(campo);
    await user.type(campo, "40");
    await user.tab();
    await waitFor(async () => expect((await api.getSettings()).gemini_espera_envio_s).toBe(15));
    await user.click(within(await screen.findByTestId("instruccion-rubrica_maxima")).getByRole("switch"));
    await user.click(screen.getByRole("button", { name: /Restaurar predeterminadas/ }));
    await waitFor(async () => {
      const lista = (await api.getSettings()).instrucciones_fijas!;
      expect(lista).toHaveLength(5);
      expect(lista.every((i) => i.activa)).toBe(true);
    });
  });

  it("envía solo las diferencias al generar y muestra el prompt", async () => {
    await api.subirImagenes("m1-t12", [new File(["x"], "p.png", { type: "image/png" })]);
    const generar = vi.spyOn(api, "generar");
    const user = userEvent.setup();
    envolver(
      <GenerarStep tareaId="m1-t12" materiaId="m1" runner={runner} onAtras={() => {}} onListo={() => {}} />,
    );
    const apa = await screen.findByRole("checkbox", { name: /Referencias APA 7/ });
    expect(apa).toBeChecked();
    await user.click(apa);
    await user.click(screen.getByRole("button", { name: /Ver prompt/ }));
    const dialogo = await screen.findByRole("dialog");
    expect(dialogo.textContent).toContain("Cumple cada criterio");
    expect(dialogo.textContent).not.toContain("## Referencias");
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: /Generar tarea/ }));
    expect(generar).toHaveBeenCalledWith("m1-t12", undefined, expect.anything(), { referencias_apa7: false });
  });
});
