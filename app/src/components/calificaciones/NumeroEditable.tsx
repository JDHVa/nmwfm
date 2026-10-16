import { useState } from "react";

export function NumeroEditable({
  etiqueta,
  valor,
  onGuardar,
  placeholder = "—",
}: {
  etiqueta: string;
  valor: number | null;
  onGuardar: (v: number | null) => void;
  placeholder?: string;
}) {
  const [texto, setTexto] = useState(valor === null ? "" : String(valor));
  const [previo, setPrevio] = useState(valor);
  if (previo !== valor) {
    setPrevio(valor);
    setTexto(valor === null ? "" : String(valor));
  }

  function guardar() {
    const limpio = texto.trim();
    if (limpio === "") {
      if (valor !== null) onGuardar(null);
      return;
    }
    const n = Number(limpio);
    if (!Number.isFinite(n)) {
      setTexto(valor === null ? "" : String(valor));
      return;
    }
    const acotado = Math.min(100, Math.max(0, n));
    setTexto(String(acotado));
    if (acotado !== valor) onGuardar(acotado);
  }

  return (
    <input
      type="number"
      inputMode="decimal"
      min={0}
      max={100}
      aria-label={etiqueta}
      placeholder={placeholder}
      value={texto}
      onChange={(e) => setTexto(e.target.value)}
      onBlur={guardar}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      className="h-8 w-20 rounded-md border bg-background px-2 text-sm tabular-nums outline-none focus-visible:ring-2 focus-visible:ring-ring"
    />
  );
}
