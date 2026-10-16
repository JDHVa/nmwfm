import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";
import { InsumosStep } from "@/views/tarea/InsumosStep";

const TAREA = "m1-t12";

describe("recursos de NEXUS y OCR", () => {
  beforeEach(async () => {
    const mock = createMockBackend({ stepMs: 2 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.subirImagenes(TAREA, [new File(["x"], "apuntes.png", { type: "image/png" })]);
  });
  afterEach(() => cleanup());

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <InsumosStep tareaId={TAREA} onContinuar={() => {}} />
      </QueryClientProvider>,
    );
  }

  it("lista los recursos y permite usarlos como insumo", async () => {
    const user = userEvent.setup();
    montar();
    const check = await screen.findByRole("checkbox", { name: "Usar como insumo: Notas de la clase.txt" });
    expect(check).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Usar como insumo: Presentación.pptx" })).toBeDisabled();
    await user.click(check);
    await waitFor(() => expect(check).toBeChecked());
    expect(check).toBeDisabled();
    expect((await api.recursos(TAREA)).find((r) => r.id === "r2")?.usado).toBe(true);
    expect((await api.insumos(TAREA)).some((i) => i.tipo === "texto")).toBe(true);
  });

  it("avisa cuando el tipo de recurso no se puede usar", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(
      await screen.findByRole("checkbox", { name: "Usar como insumo: Lectura de la unidad.pdf" }),
    );
    expect(await screen.findByText("Solo se pueden usar imágenes y texto")).toBeInTheDocument();
  });

  it("muestra el texto OCR desplegable y guarda las ediciones", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Texto detectado \(OCR\)/ }));
    const area = screen.getByLabelText("Texto detectado de la imagen 1");
    expect((area as HTMLTextAreaElement).value).toContain("apuntes.png");
    await user.clear(area);
    await user.type(area, "Texto corregido");
    await user.tab();
    await waitFor(async () => expect((await api.insumos(TAREA))[0].ocr_texto).toBe("Texto corregido"));
  });
});
