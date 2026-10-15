const CLAVE = "nmwfm.recordar";

export function leerRecordar(): boolean {
  try {
    return localStorage.getItem(CLAVE) !== "0";
  } catch {
    return true;
  }
}

export function guardarRecordar(valor: boolean) {
  try {
    localStorage.setItem(CLAVE, valor ? "1" : "0");
  } catch {
    return;
  }
}
