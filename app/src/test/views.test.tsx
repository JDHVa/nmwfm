import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

vi.mock("@/views/tarea/PdfViewer", () => ({
  default: ({ url }: { url: string }) => <div data-testid="pdf">{url}</div>,
}));

function montar() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("vistas con backend simulado", () => {
  beforeEach(() => {
    const mock = createMockBackend({ stepMs: 5 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
  });

  afterEach(() => cleanup());

  it("muestra la configuración en el primer arranque", async () => {
    montar();
    expect(await screen.findByRole("heading", { name: "Bienvenido a nmwfm" })).toBeInTheDocument();
    expect(screen.getByLabelText("Cuenta")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Iniciar sesión en Gemini/ })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Entregar sin revisar" })).toBeInTheDocument();
  });

  it("recorre materias, etapas y tarea cuando ya hay cuenta", async () => {
    await api.putSettings({ cuenta: "a1234567", nombre: "Ana", matricula: "1234567", password: "x" });
    const user = userEvent.setup();
    montar();

    expect(await screen.findByRole("heading", { name: "Materias" })).toBeInTheDocument();
    expect(await screen.findByText("Algoritmos Bio Inspirados")).toBeInTheDocument();
    expect(screen.getByText("Sistemas de Calidad")).toBeInTheDocument();
    expect(screen.getAllByText("CAVAZOS MARTÍNEZ RAFAEL ALFREDO").length).toBeGreaterThan(0);

    await user.click(screen.getByText("Algoritmos Bio Inspirados"));
    expect(await screen.findByText("Etapa 1: Algoritmos Evolutivos")).toBeInTheDocument();
    expect(await screen.findByText("Dimensión 2 - Comprensión - Ficha Técnica")).toBeInTheDocument();

    await user.click(screen.getByText("Dimensión 2 - Comprensión - Ficha Técnica"));
    expect(await screen.findByText(/Actividades de aprendizaje/i)).toBeInTheDocument();
    expect(screen.getByText(/ficha técnica del espacio de búsqueda/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Elegir archivos" })).toBeInTheDocument();
  });

  it("muestra la rúbrica en las evidencias", async () => {
    await api.putSettings({ cuenta: "a1234567", nombre: "Ana", matricula: "1234567", password: "x" });
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByText("Algoritmos Bio Inspirados"));
    const filas = await screen.findAllByText("Evidencia de Aprendizaje - Informe");
    await user.click(filas[0]);
    const tabla = await screen.findByRole("table");
    expect(within(tabla).getByText("Evidencia Completa")).toBeInTheDocument();
    expect(within(tabla).getByText("Sin Evidencia", { selector: "th" })).toBeInTheDocument();
  });

  it("sube una imagen y permite continuar a generar", async () => {
    await api.putSettings({ cuenta: "a1234567", nombre: "Ana", matricula: "1234567", password: "x" });
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByText("Algoritmos Bio Inspirados"));
    await user.click(await screen.findByText("Dimensión 2 - Comprensión - Ficha Técnica"));
    const input = await screen.findByTestId("input-archivos");
    await user.upload(input, new File(["x"], "pagina.png", { type: "image/png" }));
    await waitFor(() => expect(screen.getByRole("list", { name: "Insumos" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Continuar a generar" }));
    expect(await screen.findByRole("button", { name: /Generar tarea/ })).toBeInTheDocument();
  });
});
