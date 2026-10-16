import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

vi.mock("@/views/tarea/PdfPreview", () => ({
  default: ({ url }: { url: string }) => <div data-testid="vista-pdf">{url}</div>,
}));

describe("herramientas sueltas", () => {
  beforeEach(async () => {
    localStorage.clear();
    const mock = createMockBackend({ stepMs: 4 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana López", matricula: "1234", password: "x" });
  });
  afterEach(() => cleanup());

  async function abrir(user: ReturnType<typeof userEvent.setup>) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Asistente" }));
    await user.click(await screen.findByRole("tab", { name: "Herramientas" }));
  }

  it("convierte imágenes en un PDF descargable con vista previa", async () => {
    const user = userEvent.setup();
    await abrir(user);
    const crear = screen.getByRole("button", { name: "Crear PDF" });
    expect(crear).toBeDisabled();
    await user.upload(
      screen.getByTestId("input-herramienta-pdf"),
      new File(["x"], "foto.png", { type: "image/png" }),
    );
    expect(screen.getByRole("list", { name: "Imágenes seleccionadas" })).toBeInTheDocument();
    await user.click(crear);
    const enlace = await screen.findByRole("link", { name: /Descargar PDF/ });
    expect(enlace).toHaveAttribute("download");
    expect(enlace).toHaveAttribute("href", expect.stringContaining("blob:"));
    expect(await screen.findByTestId("vista-pdf")).toBeInTheDocument();
  });

  it("crea una portada rápida con enlaces a PDF y Word", async () => {
    const user = userEvent.setup();
    await abrir(user);
    const crear = screen.getByRole("button", { name: "Crear portada" });
    expect(crear).toBeDisabled();
    await user.type(screen.getByLabelText("Profesor"), "Rafael Cavazos");
    await user.type(screen.getByLabelText("Título"), "Ficha técnica");
    await user.click(crear);
    expect(await screen.findByRole("link", { name: /PDF de la portada/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Word de la portada/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/files/portada-suelta.docx"),
    );
    expect(await screen.findByTestId("vista-pdf")).toBeInTheDocument();
  });
});
