import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

describe("atajos de teclado", () => {
  beforeEach(async () => {
    localStorage.clear();
    const mock = createMockBackend({ stepMs: 5 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  });
  afterEach(() => cleanup());

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
  }

  async function abrirTarea(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByText("Algoritmos Bio Inspirados"));
    await user.click(await screen.findByText("Dimensión 2 - Comprensión - Ficha Técnica"));
    await screen.findByRole("button", { name: "Elegir archivos" });
  }

  it("? abre la ayuda y Esc la cierra", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await screen.findByRole("heading", { name: "Materias" });
    await user.keyboard("?");
    expect(await screen.findByRole("heading", { name: "Atajos de teclado" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Atajos de teclado" })).not.toBeInTheDocument(),
    );
  });

  it("Esc cierra el menú de sincronización", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    const mas = await screen.findByRole("button", { name: "Más opciones de sincronización" });
    await waitFor(() => expect(mas).toBeEnabled());
    await user.click(mas);
    expect(await screen.findByRole("button", { name: "Sincronizar todo de nuevo" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Sincronizar todo de nuevo" })).not.toBeInTheDocument(),
    );
  });

  it("G lleva a Generar desde Insumos", async () => {
    const user = userEvent.setup();
    montar();
    await abrirTarea(user);
    await user.keyboard("g");
    expect(await screen.findByRole("button", { name: /Generar tarea/ })).toBeInTheDocument();
  });

  it("Ctrl+V pega una imagen aunque estés en otro paso", async () => {
    const user = userEvent.setup();
    montar();
    await abrirTarea(user);
    await user.keyboard("g");
    await screen.findByRole("button", { name: /Generar tarea/ });
    const evento = new Event("paste", { bubbles: true, cancelable: true });
    Object.assign(evento, {
      clipboardData: { files: [new File(["x"], "pegada.png", { type: "image/png" })] },
    });
    document.dispatchEvent(evento);
    expect(await screen.findByRole("button", { name: "Elegir archivos" })).toBeInTheDocument();
    await waitFor(async () => expect(await api.insumos("m1-t12")).toHaveLength(1));
    fireEvent.keyDown(window, { key: "x" });
  });
});
