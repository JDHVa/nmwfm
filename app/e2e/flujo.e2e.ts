import { expect, test, type Page } from "@playwright/test";

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

async function entrar(page: Page) {
  await page.addInitScript(() => {
    if (!localStorage.getItem("nmwfm.tema")) localStorage.setItem("nmwfm.tema", "claro");
  });
  await page.goto("/");
  await page.getByLabel("Cuenta").fill("a1234567");
  await page.getByLabel("Contraseña", { exact: true }).fill("secreta");
  await page.getByLabel("Nombre completo").fill("Ana María López");
  await page.getByLabel("Matrícula").fill("1234567");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Materias" })).toBeVisible({ timeout: 20_000 });
}

async function minimizarSyncInicial(page: Page) {
  const seguir = page.getByRole("button", { name: "Seguir en segundo plano" });
  if (await seguir.isVisible().catch(() => false)) await seguir.click();
}

test("login, materias y tarea hasta entregar", async ({ page }) => {
  await entrar(page);
  await minimizarSyncInicial(page);
  await expect(page.getByText("Algoritmos Bio Inspirados")).toBeVisible();

  await page.getByText("Algoritmos Bio Inspirados").click();
  await expect(page.getByText("Etapa 1: Algoritmos Evolutivos")).toBeVisible();
  await page.getByText("Dimensión 2 - Comprensión - Ficha Técnica").click();

  await expect(page.getByRole("button", { name: "Elegir archivos" })).toBeVisible();
  await page
    .getByTestId("input-archivos")
    .setInputFiles({ name: "apuntes.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByRole("list", { name: "Insumos" })).toBeVisible();

  await page.getByRole("button", { name: "Continuar a generar" }).click();
  await expect(page.getByRole("region", { name: "Portada del documento" }).locator("canvas")).toBeVisible();
  await page.getByRole("button", { name: /Generar tarea/ }).click();

  await expect(page.getByRole("button", { name: "Continuar a entregar" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Abrir en Word" })).toBeVisible();

  await page.getByRole("button", { name: "Continuar a entregar" }).click();
  await page.getByRole("button", { name: "Entregar", exact: true }).click();
  await page.getByRole("button", { name: "Sí, entregar" }).click();
  await expect(page.getByText("Tarea entregada")).toBeVisible({ timeout: 20_000 });
});

test("búsqueda con Ctrl+K y próximas entregas", async ({ page }) => {
  await entrar(page);
  await minimizarSyncInicial(page);
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox", { name: "Buscar tareas" }).fill("mapa mental");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Etapas" })).toBeVisible();

  await page.getByRole("button", { name: "Próximas entregas" }).click();
  await expect(page.getByRole("heading", { name: "Próximas entregas" })).toBeVisible();
  await expect(page.getByRole("region", { name: /Hoy/ })).toBeVisible();
});

test("el cambio de tema se aplica y se recuerda", async ({ page }) => {
  await entrar(page);
  await minimizarSyncInicial(page);
  await page.getByRole("button", { name: "Configuración" }).click();
  await page.getByRole("radio", { name: /Oscuro/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("el asistente responde con herramientas y pide confirmación para entregar", async ({ page }) => {
  await entrar(page);
  await minimizarSyncInicial(page);
  await page.getByRole("button", { name: "Asistente" }).click();
  await page.getByRole("button", { name: "¿Qué vence esta semana?" }).click();
  const conversacion = page.getByRole("log", { name: "Conversación" });
  await expect(conversacion.getByText("Próximas entregas")).toBeVisible();
  await expect(conversacion.getByText(/La más urgente es la/)).toBeVisible({ timeout: 15_000 });

  await expect(page.getByRole("button", { name: "Enviar" })).toBeVisible({ timeout: 15_000 });
  await page.getByLabel("Mensaje").fill("entrega la tarea");
  await page.keyboard.press("Enter");
  const tarjeta = page.getByRole("region", { name: "Confirmación" });
  await expect(tarjeta).toBeVisible({ timeout: 15_000 });
  await tarjeta.getByRole("button", { name: "Aceptar" }).click();
  await expect(tarjeta.getByText(/Aceptada/)).toBeVisible();
});
