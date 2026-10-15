import type { ReactNode } from "react";

export function PageHeader({
  titulo,
  descripcion,
  acciones,
  atras,
}: {
  titulo: string;
  descripcion?: string;
  acciones?: ReactNode;
  atras?: ReactNode;
}) {
  return (
    <header className="space-y-3">
      {atras}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
          {descripcion && <p className="mt-1 text-sm text-muted-foreground">{descripcion}</p>}
        </div>
        {acciones && <div className="flex items-center gap-2">{acciones}</div>}
      </div>
    </header>
  );
}
