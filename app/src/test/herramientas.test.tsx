import { cleanup, render, screen, within } from "@testing-library/react";
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
    expect(screen.getByRole("list", { name: "Páginas del PDF" })).toBeInTheDocument();
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

  it("cada imagen es una página y se puede reordenar antes de crear el PDF", async () => {
    const espia = vi.spyOn(api, "herramientaPdf");
    const user = userEvent.setup();
    await abrir(user);
    await user.upload(screen.getByTestId("input-herramienta-pdf"), [
      new File(["a"], "uno.png", { type: "image/png" }),
      new File(["b"], "dos.png", { type: "image/png" }),
      new File(["c"], "tres.png", { type: "image/png" }),
    ]);
    const lista = screen.getByRole("list", { name: "Páginas del PDF" });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "Mover página 1 después" }));
    await user.click(screen.getByRole("button", { name: "Mover página 3 antes" }));
    const nombres = within(lista)
      .getAllByRole("img")
      .map((i) => i.getAttribute("alt"));
    expect(nombres).toEqual(["dos.png", "tres.png", "uno.png"]);
    await user.click(screen.getByRole("checkbox", { name: "Recortar cada imagen a la página" }));
    await user.click(screen.getByRole("button", { name: "Crear PDF" }));
    await screen.findByRole("link", { name: /Descargar PDF/ });
    const [archivos, recortar, portada] = espia.mock.calls[0];
    expect(archivos.map((f) => f.name)).toEqual(["dos.png", "tres.png", "uno.png"]);
    expect(recortar).toBe(false);
    expect(portada).toBeUndefined();
  });

  it("la portada solo se envía si «Agregar portada» está marcado y pide el profesor", async () => {
    const espia = vi.spyOn(api, "herramientaPdf");
    const user = userEvent.setup();
    await abrir(user);
    await user.upload(
      screen.getByTestId("input-herramienta-pdf"),
      new File(["a"], "uno.png", { type: "image/png" }),
    );
    expect(document.getElementById("pdf-portada-materia")).toBeNull();
    await user.click(screen.getByRole("checkbox", { name: "Agregar portada" }));
    const crear = screen.getByRole("button", { name: "Crear PDF" });
    expect(crear).toBeDisabled();
    await user.type(screen.getAllByLabelText("Profesor")[0], "Rafael Cavazos");
    await user.type(screen.getAllByLabelText("Título")[0], "Mapa mental");
    await user.click(crear);
    await screen.findByRole("link", { name: /Descargar PDF/ });
    expect(espia.mock.calls[0][2]).toEqual({ profesor: "Rafael Cavazos", titulo: "Mapa mental" });
  });
});
