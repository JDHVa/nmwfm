import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ATAJOS } from "@/lib/atajos";

export function AyudaAtajos({ abierto, onCerrar }: { abierto: boolean; onCerrar: () => void }) {
  return (
    <Dialog open={abierto} onOpenChange={(v) => !v && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Atajos de teclado</DialogTitle>
          <DialogDescription>Acciones rápidas disponibles en toda la aplicación.</DialogDescription>
        </DialogHeader>
        <ul className="divide-y rounded-lg border">
          {ATAJOS.map((a) => (
            <li key={a.teclas} className="flex items-center justify-between gap-4 px-3 py-2 text-sm">
              <span>{a.descripcion}</span>
              <kbd className="shrink-0 rounded border bg-muted px-2 py-0.5 text-xs font-medium">
                {a.teclas}
              </kbd>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
