import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { EstadoBadge } from "@/components/EstadoBadge";
import { api, configureApi, configureSocket } from "@/lib/api";
import { grupoDe, vencimientoDe } from "@/lib/vencimiento";
import { createMockBackend } from "@/mock/backend";

const AHORA = new Date(2026, 9, 14, 10, 0, 0);
const iso = (dias: number, h = 23, m = 59) => {
  const d = new Date(2026, 9, 14 + dias, h, m);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(h)}:${p(m)}:00`;
};

const tarea = (hasta: string | null, estado: "pendiente" | "entregada" = "pendiente") => ({
  hasta,
  estado,
  vencida: false,
});

describe("etiquetas de vencimiento", () => {
  it("muestra los días restantes con el nivel correcto", () => {
    expect(vencimientoDe(tarea(iso(10)), AHORA)).toEqual({ texto: "Vence en 10 días", nivel: "neutro" });
    expect(vencimientoDe(tarea(iso(4)), AHORA)).toEqual({ texto: "Vence en 4 días", nivel: "neutro" });
    expect(vencimientoDe(tarea(iso(3)), AHORA)).toEqual({ texto: "Vence en 3 días", nivel: "aviso" });
    expect(vencimientoDe(tarea(iso(1)), AHORA)).toEqual({ texto: "Vence mañana", nivel: "aviso" });
  });

  it("marca hoy como urgente y lo pasado como vencida", () => {
    expect(vencimientoDe(tarea(iso(0)), AHORA)).toEqual({ texto: "Vence hoy", nivel: "urgente" });
    expect(vencimientoDe(tarea(iso(0, 9, 0)), AHORA)).toEqual({ texto: "Vencida", nivel: "vencida" });
    expect(vencimientoDe(tarea(iso(-2)), AHORA)).toEqual({ texto: "Vencida", nivel: "vencida" });
  });

  it("no etiqueta las entregadas ni las que no tienen fecha", () => {
    expect(vencimientoDe(tarea(iso(2), "entregada"), AHORA)).toBeNull();
    expect(vencimientoDe(tarea(null), AHORA)).toBeNull();
  });

  it("agrupa en Hoy, Esta semana, Más adelante y Vencidas", () => {
    expect(grupoDe(tarea(iso(0)), AHORA)).toBe("Hoy");
    expect(grupoDe(tarea(iso(5)), AHORA)).toBe("Esta semana");
    expect(grupoDe(tarea(iso(20)), AHORA)).toBe("Más adelante");
    expect(grupoDe(tarea(iso(-1)), AHORA)).toBe("Vencidas");
  });
});

describe("badges de estado", () => {
  afterEach(() => cleanup());

  it("muestra la fecha de entrega y el rojo de vencida", () => {
    const { rerender } = render(
      <EstadoBadge
        tarea={{ estado: "entregada", entregada_en: "2026-10-12T18:30:00", vencida: false, hasta: null }}
      />,
    );
    expect(screen.getByText(/Entregada el 12 oct/)).toBeInTheDocument();
    rerender(
      <EstadoBadge tarea={{ estado: "pendiente", entregada_en: null, vencida: true, hasta: iso(-3) }} />,
    );
    expect(screen.getByText("Vencida")).toBeInTheDocument();
  });
});

describe("vista de próximas entregas", () => {
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

  it("agrupa las tareas pendientes y abre la tarea al hacer clic", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByRole("button", { name: "Próximas entregas" }));
    expect(await screen.findByRole("heading", { name: "Próximas entregas" })).toBeInTheDocument();
    const hoy = await screen.findByRole("region", { name: /Hoy/ });
    expect(within(hoy).getAllByText("Vence hoy").length).toBeGreaterThan(0);
    expect(await screen.findByRole("region", { name: /Vencidas/ })).toBeInTheDocument();
    const fila = within(hoy).getAllByRole("button")[0];
    await user.click(fila);
    expect(await screen.findByRole("button", { name: "Etapas" })).toBeInTheDocument();
  });

  it("revisa las tareas entregadas y resume el resultado", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByRole("button", { name: "Próximas entregas" }));
    await screen.findByRole("heading", { name: "Próximas entregas" });
    const boton = await screen.findByRole("button", { name: "Revisar tareas entregadas" });
    await waitFor(() => expect(boton).toBeEnabled(), { timeout: 5000 });
    await user.click(boton);
    expect(
      await screen.findByRole("button", { name: /\d+ entregada.*\d+ pendientes?/ }, { timeout: 8000 }),
    ).toBeInTheDocument();
  }, 15000);
});
