import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ThemeSelector } from "@/components/ThemeToggle";
import { ThemeProvider } from "@/lib/theme";

type Oyente = (e: { matches: boolean }) => void;

function simularSistema(inicialOscuro: boolean) {
  let oscuro = inicialOscuro;
  const oyentes = new Set<Oyente>();
  window.matchMedia = ((query: string) => ({
    get matches() {
      return query.includes("dark") ? oscuro : false;
    },
    media: query,
    addEventListener: (_: string, fn: Oyente) => oyentes.add(fn),
    removeEventListener: (_: string, fn: Oyente) => oyentes.delete(fn),
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
    onchange: null,
  })) as unknown as typeof window.matchMedia;
  return (valor: boolean) => {
    oscuro = valor;
    oyentes.forEach((fn) => fn({ matches: valor }));
  };
}

const montar = () =>
  render(
    <ThemeProvider>
      <ThemeSelector />
    </ThemeProvider>,
  );

describe("tema", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });
  afterEach(() => cleanup());

  it("sigue el tema del sistema y reacciona a sus cambios", () => {
    const cambiar = simularSistema(true);
    montar();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("radio", { name: /Sistema/ })).toHaveAttribute("aria-checked", "true");
    act(() => cambiar(false));
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("permite forzar claro u oscuro y lo recuerda", async () => {
    simularSistema(true);
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("radio", { name: /Claro/ }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("nmwfm.tema")).toBe("claro");
    await user.click(screen.getByRole("radio", { name: /Oscuro/ }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("nmwfm.tema")).toBe("oscuro");
  });

  it("restaura el tema guardado al abrir", () => {
    simularSistema(false);
    localStorage.setItem("nmwfm.tema", "oscuro");
    montar();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("radio", { name: /Oscuro/ })).toHaveAttribute("aria-checked", "true");
  });
});
