import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { createMockBackend } from "@/mock/backend";

function montar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

async function llenar(user: ReturnType<typeof userEvent.setup>, password = "secreta") {
  await user.type(await screen.findByLabelText("Cuenta"), "a1234567");
  await user.type(screen.getByLabelText("Contraseña"), password);
  await user.type(screen.getByLabelText("Nombre completo"), "Ana María López");
  await user.type(screen.getByLabelText("Matrícula"), "1234567");
}

describe("login", () => {
  beforeEach(() => {
    localStorage.clear();
    const mock = createMockBackend({ stepMs: 5 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
  });

  afterEach(() => cleanup());

  it("el ojo alterna entre ocultar y mostrar la contraseña", async () => {
    const user = userEvent.setup();
    montar();
    const campo = await screen.findByLabelText("Contraseña");
    expect(campo).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Mostrar contraseña" }));
    expect(campo).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: "Ocultar contraseña" }));
    expect(campo).toHaveAttribute("type", "password");
  });

  it("avisa cuando Bloq Mayús está activado", async () => {
    montar();
    const campo = await screen.findByLabelText("Contraseña");
    fireEvent.keyDown(campo, { key: "A", modifierCapsLock: true });
    expect(await screen.findByText("Bloq Mayús está activado")).toBeInTheDocument();
    fireEvent.keyUp(campo, { key: "A", modifierCapsLock: false });
    await waitFor(() => expect(screen.queryByText("Bloq Mayús está activado")).not.toBeInTheDocument());
  });

  it("valida con SIASE y entra al Asistente", async () => {
    const user = userEvent.setup();
    montar();
    await llenar(user);
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByText("Verificando con SIASE...")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Asistente" }, { timeout: 20000 })).toBeInTheDocument();
    expect(localStorage.getItem("nmwfm.recordar")).toBe("1");
  });

  it("muestra el error de SIASE y no avanza", async () => {
    const user = userEvent.setup();
    montar();
    await llenar(user, "mala");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(
      await screen.findByText("La cuenta o la contraseña son incorrectas", {}, { timeout: 20000 }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Asistente" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeEnabled();
  });

  it("permite continuar sin verificar", async () => {
    const user = userEvent.setup();
    montar();
    await llenar(user, "mala");
    await user.click(screen.getByRole("button", { name: "Continuar sin verificar" }));
    expect(await screen.findByRole("heading", { name: "Asistente" })).toBeInTheDocument();
  });

  it("con la sesión recordada saluda por el primer nombre y abre el Asistente", async () => {
    await api.putSettings({ cuenta: "a1", nombre: "Ana María López", matricula: "1", password: "x" });
    const user = userEvent.setup();
    montar();
    const saludo = await screen.findByRole("button", { name: /Hola, Ana/ });
    await user.click(saludo);
    expect(await screen.findByRole("heading", { name: "Asistente" })).toBeInTheDocument();
  });

  it("sin recordar muestra el login con la cuenta prellenada", async () => {
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
    localStorage.setItem("nmwfm.recordar", "0");
    montar();
    expect(await screen.findByLabelText("Cuenta")).toHaveValue("a1");
  });
});
