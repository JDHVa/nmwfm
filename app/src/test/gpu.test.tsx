import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

async function preparar(cargaModeloMs = 5) {
  localStorage.clear();
  const mock = createMockBackend({ stepMs: 4, cargaModeloMs });
  configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
  configureSocket(mock.createSocket);
  await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  return mock;
}

function montar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

async function entrar(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /Hola/ }));
}

describe("memoria de video del asistente", () => {
  afterEach(() => cleanup());

  it("precalienta al entrar, muestra «Cargando modelo…» y libera al salir", async () => {
    const mock = await preparar(400);
    const user = userEvent.setup();
    montar();
    await entrar(user);
    expect(await screen.findByText("Cargando modelo…")).toBeInTheDocument();
    expect(mock.llamadas).toContain("POST /asistente/precalentar");
    await waitFor(() => expect(screen.queryByText("Cargando modelo…")).not.toBeInTheDocument());
    expect(mock.llamadas).not.toContain("POST /asistente/liberar");

    await user.click(screen.getByRole("button", { name: "Materias" }));
    await waitFor(() => expect(mock.llamadas).toContain("POST /asistente/liberar"));
  });

  it("muestra «Cargando modelo…» en la burbuja hasta que llega la respuesta", async () => {
    await preparar(400);
    const user = userEvent.setup();
    montar();
    await entrar(user);
    await user.click(await screen.findByRole("button", { name: "Asistente" }));
    await waitFor(() => expect(screen.queryByText("Cargando modelo…")).not.toBeInTheDocument());
    await user.type(screen.getByLabelText("Mensaje"), "hola{Enter}");
    const conversacion = screen.getByRole("log", { name: "Conversación" });
    expect(await within(conversacion).findByText("Cargando modelo…")).toBeInTheDocument();
    expect(
      await within(conversacion).findByText(/asistente simulado/, undefined, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(within(conversacion).queryByText("Cargando modelo…")).not.toBeInTheDocument();
  });

  it("libera la GPU al cerrar la aplicación", async () => {
    const mock = await preparar();
    const user = userEvent.setup();
    montar();
    await entrar(user);
    await screen.findByRole("heading", { name: "Asistente" });
    window.dispatchEvent(new Event("pagehide"));
    await waitFor(() => expect(mock.llamadas).toContain("POST /asistente/liberar"));
  });

  it("permite configurar los segundos para liberar la GPU", async () => {
    await preparar();
    const user = userEvent.setup();
    montar();
    await entrar(user);
    await user.click(await screen.findByRole("button", { name: "Configuración" }));
    const campo = await screen.findByLabelText("Liberar GPU tras N segundos");
    expect(campo).toHaveValue(90);
    await user.clear(campo);
    await user.type(campo, "30");
    await user.tab();
    await waitFor(async () => expect((await api.getSettings()).asistente_keep_alive_s).toBe(30));
  });
});
