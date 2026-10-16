import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";
import { RevisarStep } from "@/views/tarea/RevisarStep";

vi.mock("@/views/tarea/PdfViewer", () => ({
  default: ({ url }: { url: string }) => <div data-testid="pdf">{url}</div>,
}));

const TAREA = "m1-t12";

async function generar() {
  const job = await api.generar(TAREA);
  await waitFor(async () => expect((await api.job(job.id)).estado).toBe("ok"));
}

describe("historial de generaciones", () => {
  beforeEach(async () => {
    const mock = createMockBackend({ stepMs: 2 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
    await api.subirImagenes(TAREA, [new File(["x"], "p.png", { type: "image/png" })]);
    await generar();
  });
  afterEach(() => cleanup());

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <RevisarStep tareaId={TAREA} onRegenerar={() => {}} onContinuar={() => {}} />
      </QueryClientProvider>,
    );
  }

  it("no muestra historial con una sola versión", async () => {
    montar();
    await screen.findByTestId("pdf");
    expect(screen.queryByText("Historial de versiones")).not.toBeInTheDocument();
  });

  it("lista versiones, compara dos y restaura una anterior", async () => {
    await generar();
    const user = userEvent.setup();
    montar();
    expect(await screen.findByText("Historial de versiones")).toBeInTheDocument();
    const v1 = (await screen.findByText("Versión 1")).closest("li")!;
    const v2 = screen.getAllByText("Versión 2")[0].closest("li")!;
    expect(within(v2).getByText("Actual")).toBeInTheDocument();
    expect(within(v1).queryByText("Actual")).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Comparar versión 1" }));
    await user.click(screen.getByRole("checkbox", { name: "Comparar versión 2" }));
    const comparacion = await screen.findByRole("region", { name: "Comparación" });
    expect(await within(comparacion).findAllByTestId("pdf")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "Restaurar versión 1" }));
    await waitFor(() =>
      expect(
        within(screen.getAllByText("Versión 1")[0].closest("li")!).getByText("Actual"),
      ).toBeInTheDocument(),
    );
    expect(
      within(screen.getAllByText("Versión 2")[0].closest("li")!).queryByText("Actual"),
    ).not.toBeInTheDocument();
  });
});
