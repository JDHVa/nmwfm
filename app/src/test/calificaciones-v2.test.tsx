import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { api, configureApi, configureSocket } from "@/lib/api";
import { porcentaje, promedio, puntosDeMaximo } from "@/lib/calificaciones";
import { createMockBackend } from "@/mock/backend";

describe("formatos de calificaciones v2", () => {
  it("muestra «<1 %» para probabilidades diminutas pero no nulas", () => {
    expect(porcentaje(0.003)).toBe("<1 %");
    expect(porcentaje(0)).toBe("0 %");
    expect(porcentaje(0.005)).toBe("1 %");
    expect(porcentaje(null)).toBe("—");
  });

  it("formatea puntos sobre máximo y promedios", () => {
    expect(puntosDeMaximo(12.5, 40)).toBe("12.5 / 40");
    expect(puntosDeMaximo(0, 0)).toBe("—");
    expect(promedio([])).toBeNull();
    expect(promedio([80, 90])).toBe(85);
  });
});

describe("calificaciones v2 en la vista", () => {
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

  it("pone la tabla resumen arriba con las columnas y el promedio", async () => {
    await abrir();
    const tabla = await screen.findByRole("region", { name: "Tabla resumen de calificaciones" });
    for (const nombre of ["Materia", "Tipo", "Portafolio", "Exámenes", "Total acumulado", "% sobre lo evaluado"]) {
      expect(within(tabla).getByRole("columnheader", { name: nombre })).toBeInTheDocument();
    }
    expect(within(tabla).getByRole("columnheader", { name: /Proyectada/ })).toBeInTheDocument();
    expect(within(tabla).getByRole("rowheader", { name: "Promedio del semestre" })).toBeInTheDocument();
    const resumen = screen.getByRole("region", { name: "Resumen del semestre" });
    expect(tabla.compareDocumentPosition(resumen) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(await screen.findByTestId("fila-033")).getByText("Bachillerato")).toBeInTheDocument();
  });

  it("marca la materia en cuidado y lista sus alertas en la tarjeta", async () => {
    await abrir();
    const fila = await screen.findByTestId("fila-672");
    expect(within(fila).getByRole("img", { name: /Cuidado: .*Examen bajo/ })).toBeInTheDocument();
    const tarjeta = await screen.findByRole("article", { name: "Desarrollo de Aplicaciones Móviles" });
    const alertas = within(tarjeta).getByRole("list", { name: /Alertas de/ });
    expect(within(alertas).getByText(/Examen bajo/)).toBeInTheDocument();
    expect(within(screen.getByTestId("fila-095")).queryByRole("img", { name: /Cuidado/ })).toBeNull();
  });

  it("revisa el portafolio en NEXUS con progreso y actualiza la fecha", async () => {
    const user = await abrir();
    expect(await screen.findByText(/portafolio de NEXUS: nunca/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Revisar portafolio en NEXUS" }));
    expect(await screen.findByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("Terminado")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/portafolio de NEXUS: nunca/)).toBeNull());
  });

  it("cambia de escenario y recalcula la columna proyectada y el promedio", async () => {
    const user = await abrir();
    await screen.findByTestId("promedio-proyectado");
    await user.click(screen.getByRole("button", { name: "Optimista" }));
    await screen.findByRole("columnheader", { name: /Proyectada · Optimista/ });
    let optimista = 0;
    await waitFor(() => {
      optimista = Number(screen.getByTestId("promedio-proyectado").textContent);
      expect(optimista).toBeGreaterThan(85);
    });
    await user.click(screen.getByRole("button", { name: "Pesimista" }));
    await waitFor(() => expect(Number(screen.getByTestId("promedio-proyectado").textContent)).toBeLessThan(optimista));
  });

  it("mover un deslizador global pasa a Personalizado y Restablecer vuelve a Mío", async () => {
    const user = await abrir();
    const panel = await screen.findByRole("region", { name: "Escenarios" });
    expect(within(panel).getByRole("button", { name: "Mío" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.change(within(panel).getByLabelText("Exámenes"), { target: { value: "50" } });
    expect(within(panel).getByRole("button", { name: "Personalizado" })).toHaveAttribute("aria-pressed", "true");
    expect(within(panel).getByLabelText("Exámenes")).toHaveValue("50");
    await user.click(within(panel).getByRole("button", { name: /Restablecer/ }));
    expect(within(panel).getByRole("button", { name: "Mío" })).toHaveAttribute("aria-pressed", "true");
    expect(within(panel).getByLabelText("Exámenes")).not.toHaveValue("50");
  });

  it("permite fijar la nota de un pendiente y activar el esfuerzo por materia", async () => {
    const user = await abrir();
    const panel = await screen.findByRole("region", { name: "Escenarios" });
    await user.click(within(panel).getByRole("button", { name: /Lógica/ }));
    await user.type(within(panel).getByLabelText("Nota de Silogismos en Lógica"), "100{Enter}");
    expect(within(panel).getByText("ajustada")).toBeInTheDocument();
    const esfuerzo = within(panel).getByRole("switch", { name: "Le voy a echar ganas en Lógica" });
    await user.click(esfuerzo);
    expect(esfuerzo).toBeChecked();
  });

  it("muestra el resumen del historial", async () => {
    await abrir();
    const historial = await screen.findByRole("region", { name: "Historial" });
    expect(await within(historial).findByRole("rowheader", { name: "Parcial 1" })).toBeInTheDocument();
    expect(within(historial).getByRole("rowheader", { name: "Total" })).toBeInTheDocument();
    expect(within(historial).getByRole("columnheader", { name: "Sacó 100" })).toBeInTheDocument();
  });
});
