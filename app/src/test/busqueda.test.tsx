import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket, type Tarea } from "@/lib/api";
import { FILTROS_VACIOS, buscarTareas, cumpleFiltros } from "@/lib/filtros";
import { createMockBackend } from "@/mock/backend";

const base: Tarea = {
  id: "t1",
  etapa_id: "e1",
  materia_id: "m1",
  numero: "1.2",
  titulo: "Dimensión 2 - Comprensión - Ficha Técnica",
  tipo: "dimension",
  desde: null,
  hasta: "2026-10-20T23:59:00",
  puntos: 2.5,
  modalidad: null,
  estado: "pendiente",
  entregada_en: null,
  vencida: false,
};

describe("búsqueda y filtros", () => {
  it("busca por título, materia o número sin importar acentos", () => {
    const items = [
      { tarea: base, materia: "Lógica" },
      { tarea: { ...base, id: "t2", numero: "3.4", titulo: "Reporte de práctica" }, materia: "Algoritmos" },
    ];
    expect(buscarTareas(items, "comprension")).toHaveLength(1);
    expect(buscarTareas(items, "algoritmos")[0].tarea.id).toBe("t2");
    expect(buscarTareas(items, "3.4")[0].tarea.id).toBe("t2");
    expect(buscarTareas(items, "logica ficha")).toHaveLength(1);
    expect(buscarTareas(items, "zzz")).toHaveLength(0);
  });

  it("filtra por tipo, estado y rango de fechas", () => {
    expect(cumpleFiltros(base, { ...FILTROS_VACIOS, tipo: "examen" })).toBe(false);
    expect(cumpleFiltros(base, { ...FILTROS_VACIOS, tipo: "dimension" })).toBe(true);
    expect(cumpleFiltros(base, { ...FILTROS_VACIOS, estado: "vencida" })).toBe(false);
    expect(cumpleFiltros({ ...base, vencida: true }, { ...FILTROS_VACIOS, estado: "vencida" })).toBe(true);
    expect(cumpleFiltros(base, { ...FILTROS_VACIOS, desde: "2026-10-21" })).toBe(false);
    expect(cumpleFiltros(base, { ...FILTROS_VACIOS, desde: "2026-10-20", hasta: "2026-10-20" })).toBe(true);
  });
});

describe("paleta y filtros en la interfaz", () => {
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

  it("Ctrl+K abre la paleta y Enter abre la tarea elegida", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await screen.findByRole("heading", { name: "Materias" });
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    const campo = await screen.findByRole("combobox", { name: "Buscar tareas" });
    await user.type(campo, "mapa mental lógica");
    expect(await screen.findByText("Dimensión 3 - Análisis - Mapa mental")).toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("button", { name: "Etapas" })).toBeInTheDocument();
  });

  it("la paleta ofrece Calificaciones y Enter abre la vista", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await screen.findByRole("heading", { name: "Materias" });
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    const campo = await screen.findByRole("combobox", { name: "Buscar tareas" });
    expect(screen.queryByText("Ir a la sección")).not.toBeInTheDocument();
    await user.type(campo, "calificaciones");
    expect(await screen.findByText("Ir a la sección")).toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { name: "Calificaciones" })).toBeInTheDocument();
  });

  it("filtra las próximas entregas por estado", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Hola/ }));
    await user.click(await screen.findByRole("button", { name: "Materias" }));
    await user.click(await screen.findByRole("button", { name: "Próximas entregas" }));
    await screen.findByRole("region", { name: /Hoy/ });
    await user.selectOptions(screen.getByLabelText("Estado"), "vencida");
    expect(await screen.findByRole("region", { name: /Vencidas/ })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /Hoy/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Limpiar filtros/ }));
    expect(await screen.findByRole("region", { name: /Hoy/ })).toBeInTheDocument();
  });
});
