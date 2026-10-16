import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket, type MateriaCalificacion } from "@/lib/api";
import { finalSimulada, ordenarMaterias, segmentosBarra } from "@/lib/calificaciones";
import { createMockBackend } from "@/mock/backend";

const materia = (parcial: Partial<MateriaCalificacion>): MateriaCalificacion => ({
  clave: "x",
  nombre: "X",
  materia_id: null,
  tipo: "bachillerato",
  tipo_manual: false,
  componentes: [],
  portafolio: [],
  pendientes: [],
  asegurados: 0,
  maximo_posible: 100,
  proyectada: 80,
  rango: [70, 90],
  objetivo: null,
  necesario: null,
  alcanzable: true,
  prob_objetivo: null,
  prob_aprobar: 0.9,
  estado: "bien",
  alertas: [],
  en_cuidado: false,
  portafolio_pts: 0,
  portafolio_max: 40,
  examenes_pts: 0,
  examenes_max: 60,
  total_pts: 0,
  evaluado_pts: 0,
  pct_evaluado: null,
  ...parcial,
});

describe("cálculo local de calificaciones", () => {
  it("suma asegurados más calificación por peso de cada pendiente", () => {
    const m = materia({
      asegurados: 40,
      pendientes: [
        { clave: "eg", titulo: "Examen global", peso: 25 },
        { clave: "portafolio", titulo: "Proyecto", peso: 10 },
      ],
    });
    expect(finalSimulada(m, { 0: 80, 1: 100 })).toBe(70);
    expect(finalSimulada(m, { 0: 0, 1: 0 })).toBe(40);
  });

  it("ordena en riesgo primero", () => {
    const orden = ordenarMaterias(
      [
        materia({ clave: "a", estado: "bien" }),
        materia({ clave: "b", estado: "sin_datos" }),
        materia({ clave: "c", estado: "riesgo" }),
        materia({ clave: "d", estado: "atento" }),
      ],
      "riesgo",
    ).map((m) => m.clave);
    expect(orden).toEqual(["c", "d", "a", "b"]);
  });

  it("reparte la barra entre asegurado, pendiente y perdido", () => {
    expect(segmentosBarra(materia({ asegurados: 50, maximo_posible: 90 }))).toEqual({
      asegurado: 50,
      pendiente: 40,
      perdido: 10,
    });
  });
});

describe("vista de calificaciones", () => {
  beforeEach(async () => {
    localStorage.clear();
    const mock = createMockBackend({ stepMs: 5 });
    configureApi({ base: "http://127.0.0.1:8765", token: "dev", transport: mock.transport });
    configureSocket(mock.createSocket);
    await api.putSettings({ cuenta: "a1", nombre: "Ana", matricula: "1", password: "x" });
  });
  afterEach(() => cleanup());

  async function abrir() {
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Calificaciones" }));
    await screen.findByRole("heading", { name: "Calificaciones" });
    return user;
  }

  it("muestra el semestre y las materias con el riesgo primero", async () => {
    await abrir();
    const resumen = await screen.findByRole("region", { name: "Resumen del semestre" });
    expect(within(resumen).getByText("Promedio actual")).toBeInTheDocument();
    expect(within(resumen).getByLabelText("Objetivo del semestre")).toHaveValue(90);
    const tarjetas = await screen.findAllByRole("article");
    expect(tarjetas.length).toBe(10);
    expect(within(tarjetas[0]).getByText("En riesgo")).toBeInTheDocument();
  });

  it("guarda el objetivo de una materia y cambia el tipo", async () => {
    const user = await abrir();
    const tarjeta = await screen.findByRole("article", { name: "Lógica" });
    const campo = within(tarjeta).getByLabelText("Objetivo de Lógica");
    await user.type(campo, "88{Enter}");
    expect(await within(tarjeta).findByText(/Necesitas/)).toBeInTheDocument();
    await user.selectOptions(within(tarjeta).getByLabelText("Tipo de Lógica"), "carrera");
    expect(await within(tarjeta).findByRole("button", { name: "Detectar solo" })).toBeInTheDocument();
  });

  it("el simulador recalcula la final exacta", async () => {
    const user = await abrir();
    const tarjeta = await screen.findByRole("article", { name: "Lógica" });
    await user.click(within(tarjeta).getByRole("button", { name: /Ver detalle/ }));
    const antes = within(tarjeta).getByTestId("final-033").textContent;
    const control = within(tarjeta).getAllByRole("slider")[0] as HTMLInputElement;
    fireEvent.change(control, { target: { value: "100" } });
    expect(within(tarjeta).getByTestId("final-033").textContent).not.toBe(antes);
    expect(within(tarjeta).getAllByText("sin calificar").length).toBeGreaterThan(0);
  });

  it("revisa en SIASE y muestra el progreso", async () => {
    const user = await abrir();
    await user.click(screen.getByRole("button", { name: /Revisar calificaciones en SIASE/ }));
    expect(await screen.findByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("Terminado")).toBeInTheDocument();
  });
});
