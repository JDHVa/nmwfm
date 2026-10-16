import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { api, configureApi, configureSocket } from "@/lib/api";
import { NavProvider } from "@/lib/app-context";
import { createMockBackend } from "@/mock/backend";
import { ConfigView } from "@/views/ConfigView";

describe("sesión de Gemini", () => {
  beforeEach(async () => {
    const mock = createMockBackend({ stepMs: 2 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  });
  afterEach(() => cleanup());

  function montar() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <NavProvider initial={{ name: "config" }}>
          <ConfigView />
        </NavProvider>
      </QueryClientProvider>,
    );
  }

  it("sin verificar: verificar deja la sesión guardada", async () => {
    const user = userEvent.setup();
    montar();
    expect(await screen.findByText("Sesión sin verificar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Iniciar sesión en Gemini" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Verificar sesión" }));
    expect(await screen.findByText("Sesión de Gemini guardada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Volver a iniciar sesión" })).toBeInTheDocument();
  });

  it("el login deja la sesión guardada", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: "Iniciar sesión en Gemini" }));
    expect(await screen.findByText("Sesión de Gemini guardada")).toBeInTheDocument();
  });

  it("sesión cerrada: avisa y solo ofrece iniciar sesión", async () => {
    const mock = createMockBackend({ stepMs: 2 });
    configureApi({
      base: "http://127.0.0.1:8765",
      token: "dev",
      transport: async (url, init) => {
        const res = await mock.transport(url, init);
        if (url.endsWith("/settings") && (init.method ?? "GET") === "GET") {
          return new Response(JSON.stringify({ ...(await res.json()), gemini_sesion: false }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return res;
      },
    });
    montar();
    expect(await screen.findByText("La sesión de Gemini se cerró")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Iniciar sesión en Gemini" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verificar sesión" })).not.toBeInTheDocument();
  });
});
