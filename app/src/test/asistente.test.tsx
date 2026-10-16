import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { api, chatAsistente, configureApi, configureSocket, type EventoChat } from "@/lib/api";
import { createMockBackend, type MockOptions } from "@/mock/backend";

async function preparar(opciones: MockOptions = {}) {
  localStorage.clear();
  const mock = createMockBackend({ stepMs: 4, ...opciones });
  configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
  configureSocket(mock.createSocket);
  await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
}

function montar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

async function abrirAsistente(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /Hola/ }));
  await user.click(await screen.findByRole("button", { name: "Asistente" }));
  await screen.findByRole("heading", { name: "Asistente" });
}

describe("flujo SSE del cliente", () => {
  beforeEach(() => preparar());

  it("entrega los eventos en orden", async () => {
    const eventos: EventoChat[] = [];
    await chatAsistente({ mensajes: [{ rol: "user", contenido: "¿Qué vence esta semana?" }] }, (e) =>
      eventos.push(e),
    );
    expect(eventos[0].type).toBe("estado");
    expect(eventos[1].type).toBe("tool_call");
    expect(eventos.some((e) => e.type === "token")).toBe(true);
    expect(eventos[eventos.length - 1].type).toBe("fin");
  });
});

describe("vista del asistente", () => {
  afterEach(() => cleanup());

  it("responde con streaming, Markdown y chips de herramientas desplegables", async () => {
    await preparar();
    const user = userEvent.setup();
    montar();
    await abrirAsistente(user);
    await user.click(screen.getByRole("button", { name: "¿Qué vence esta semana?" }));
    const conversacion = screen.getByRole("log", { name: "Conversación" });
    expect(await within(conversacion).findByText("¿Qué vence esta semana?")).toBeInTheDocument();
    await waitFor(() => expect(within(conversacion).getAllByRole("listitem").length).toBeGreaterThan(1), {
      timeout: 5000,
    });
    expect(
      await within(conversacion).findByText(/La más urgente es la/, undefined, { timeout: 5000 }),
    ).toBeInTheDocument();
    const chip = within(conversacion).getByText("Próximas entregas");
    expect(chip.closest("details")).not.toHaveAttribute("open");
    await user.click(chip);
    expect(chip.closest("details")).toHaveAttribute("open");
    expect(within(conversacion).getByText("Argumentos")).toBeInTheDocument();
  });

  it("pide confirmación antes de entregar y la resuelve con Aceptar", async () => {
    await preparar();
    const user = userEvent.setup();
    montar();
    await abrirAsistente(user);
    await user.type(screen.getByLabelText("Mensaje"), "entrega la tarea{Enter}");
    const tarjeta = await screen.findByRole("region", { name: "Confirmación" }, { timeout: 5000 });
    expect(tarjeta).toHaveTextContent("quiere entregar");
    await user.click(within(tarjeta).getByRole("button", { name: "Aceptar" }));
    expect(await within(tarjeta).findByText(/Aceptada: La tarea se entregó/)).toBeInTheDocument();
  });

  it("guarda el historial y «Nueva conversación» lo borra", async () => {
    await preparar();
    const user = userEvent.setup();
    const { unmount } = montar();
    await abrirAsistente(user);
    await user.type(screen.getByLabelText("Mensaje"), "hola{Enter}");
    await screen.findByText(/asistente simulado/, undefined, { timeout: 5000 });
    expect(localStorage.getItem("nmwfm.chat")).toContain("hola");
    unmount();
    cleanup();

    const segunda = userEvent.setup();
    montar();
    await abrirAsistente(segunda);
    expect(await screen.findByText(/asistente simulado/)).toBeInTheDocument();
    await segunda.click(screen.getByRole("button", { name: /Nueva conversación/ }));
    expect(screen.queryByText(/asistente simulado/)).not.toBeInTheDocument();
    expect(localStorage.getItem("nmwfm.chat")).toBeNull();
  }, 20000);

  it("adjunta imágenes, crea el PDF y muestra el enlace", async () => {
    await preparar();
    const user = userEvent.setup();
    montar();
    await abrirAsistente(user);
    await user.upload(
      screen.getByTestId("adjuntar-chat"),
      new File(["x"], "foto.png", { type: "image/png" }),
    );
    expect(screen.getByRole("list", { name: "Adjuntos" })).toHaveTextContent("foto.png");
    await user.type(screen.getByLabelText("Mensaje"), "hazme un pdf{Enter}");
    expect(await screen.findByText(/Se unieron 1 imagen/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Abrir PDF/ })).toHaveAttribute(
      "href",
      expect.stringContaining("blob:"),
    );
  });

  it("muestra instrucciones si no hay Ollama y no rompe la vista", async () => {
    await preparar({ asistenteDisponible: false });
    const user = userEvent.setup();
    montar();
    await abrirAsistente(user);
    const tarjeta = await screen.findByRole("region", { name: "Asistente no disponible" });
    expect(tarjeta).toHaveTextContent("ollama pull qwen3:4b");
    expect(screen.getByLabelText("Mensaje")).toBeDisabled();
  });
});

describe("preguntar al asistente desde una tarea", () => {
  afterEach(() => cleanup());

  it("abre el chat con el contexto de la tarea", async () => {
    await preparar();
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByText("Algoritmos Bio Inspirados"));
    await user.click(await screen.findByText("Dimensión 2 - Comprensión - Ficha Técnica"));
    await user.click(await screen.findByRole("button", { name: "Preguntar al asistente" }));
    expect(await screen.findByText(/Contexto: tarea/)).toBeInTheDocument();
    expect(screen.getByText(/Dimensión 2 - Comprensión - Ficha Técnica/)).toBeInTheDocument();
  });
});
