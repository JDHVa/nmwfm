import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, configureApi, fileUrl } from "@/lib/api";

function respuesta(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status });
}

describe("cliente api", () => {
  const transport = vi.fn();

  beforeEach(() => {
    transport.mockReset();
    configureApi({ base: "http://127.0.0.1:9999", token: "secreto", transport });
  });

  afterEach(() => {
    configureApi({ base: "http://127.0.0.1:8765", token: "dev" });
  });

  it("envía el header X-Token y la URL base", async () => {
    transport.mockResolvedValue(respuesta([]));
    await api.materias();
    const [url, init] = transport.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:9999/materias");
    expect(new Headers(init.headers).get("X-Token")).toBe("secreto");
    expect(init.method).toBe("GET");
  });

  it("serializa JSON en el cuerpo y marca el content-type", async () => {
    transport.mockResolvedValue(respuesta({ id: "job-1" }));
    await api.generar("t1", "sé breve");
    const [url, init] = transport.mock.calls[0];
    expect(url).toContain("/tareas/t1/generar");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ instrucciones_extra: "sé breve" });
  });

  it("envía multipart con files[] sin forzar content-type", async () => {
    transport.mockResolvedValue(respuesta([]));
    await api.subirImagenes("t1", [new File(["x"], "a.png", { type: "image/png" })]);
    const [, init] = transport.mock.calls[0];
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).getAll("files[]")).toHaveLength(1);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("devuelve undefined en respuestas 204", async () => {
    transport.mockResolvedValue(respuesta(null, 204));
    await expect(api.borrarInsumo("i1")).resolves.toBeUndefined();
  });

  it("convierte errores del contrato en ApiError", async () => {
    transport.mockResolvedValue(
      respuesta({ error: { code: "sin_insumos", message: "Faltan insumos" } }, 400),
    );
    const error = await api.generar("t1").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 400, code: "sin_insumos", message: "Faltan insumos" });
  });

  it("maneja errores sin cuerpo JSON", async () => {
    transport.mockResolvedValue(new Response("boom", { status: 500, statusText: "Server Error" }));
    const error = await api.getSettings().catch((e) => e);
    expect(error).toMatchObject({ status: 500, code: "http_error" });
  });

  it("reporta falta de conexión", async () => {
    transport.mockRejectedValue(new TypeError("fetch failed"));
    const error = await api.health().catch((e) => e);
    expect(error).toMatchObject({ status: 0, code: "sin_conexion" });
  });

  it("construye URLs de archivos con token", () => {
    expect(fileUrl("/files/a.png")).toBe("http://127.0.0.1:9999/files/a.png?token=secreto");
    expect(fileUrl("data:image/png;base64,AA")).toBe("data:image/png;base64,AA");
    expect(fileUrl(undefined)).toBe("");
  });
});
