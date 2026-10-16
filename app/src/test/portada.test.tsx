import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, configureApi, configureSocket } from "@/lib/api";
import { NavProvider } from "@/lib/app-context";
import { createMockBackend } from "@/mock/backend";
import { GenerarStep } from "@/views/tarea/GenerarStep";

vi.mock("@/views/tarea/PdfPreview", () => ({
  default: ({ url }: { url: string }) => <div data-testid="portada-pdf">{url}</div>,
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

  it("muestra la vista previa de la portada como PDF", async () => {
    montar();
    expect(await screen.findByRole("region", { name: "Portada del documento" })).toBeInTheDocument();
    const pdf = await screen.findByTestId("portada-pdf");
    expect(pdf.textContent).toContain("blob:");
  });

  it("genera con las instrucciones extra", async () => {
    const generar = vi.spyOn(api, "generar");
    const user = userEvent.setup();
    montar();
    await user.type(screen.getByLabelText(/Instrucciones extra/), "Sé breve");
    await user.click(screen.getByRole("button", { name: /Generar tarea/ }));
    expect(generar).toHaveBeenCalledWith(
      "m1-t12",
      "Sé breve",
      {
        profesor: "CAVAZOS MARTÍNEZ RAFAEL ALFREDO",
        aula: "144",
        grupo: "5V1",
        turno: "MATUTINO",
        especialidad: "Técnico en Inteligencia Artificial BPI",
      },
      undefined,
    );
  });

  it("prellena la portada con la configuración y el profesor sugerido", async () => {
    const preview = vi.spyOn(api, "portadaPreview");
    const user = userEvent.setup();
    montar();
    const aula = await screen.findByLabelText("Aula");
    await waitFor(() => expect(aula).toHaveValue("144"));
    expect(screen.queryByLabelText("Materia")).toBeNull();
    expect(screen.queryByLabelText("Título")).toBeNull();
    const profesor = screen.getByRole("combobox", { name: "Profesor" });
    await waitFor(() => expect(profesor).toHaveValue("CAVAZOS MARTÍNEZ RAFAEL ALFREDO"));
    await user.clear(profesor);
    expect(await screen.findByRole("option", { name: /CAVAZOS/ })).toHaveTextContent(
      "Algoritmos Bio Inspirados",
    );
    await user.click(screen.getByRole("option", { name: /CAVAZOS/ }));
    expect(profesor).toHaveValue("CAVAZOS MARTÍNEZ RAFAEL ALFREDO");
    expect(preview).toHaveBeenCalled();
  });
});
