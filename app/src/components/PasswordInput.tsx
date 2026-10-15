import { useState, type KeyboardEvent } from "react";
import { Eye, EyeOff, TriangleAlert } from "lucide-react";
import { Input } from "@/components/ui/input";

export function PasswordInput({
  id,
  value,
  onChange,
  placeholder,
  autoComplete = "current-password",
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
}) {
  const [visible, setVisible] = useState(false);
  const [mayusculas, setMayusculas] = useState(false);
  const detectar = (e: KeyboardEvent<HTMLInputElement>) => setMayusculas(e.getModifierState("CapsLock"));

  return (
    <div className="space-y-1.5">
      <div className="relative">
        <Input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          placeholder={placeholder}
          value={value}
          className="pr-10"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={detectar}
          onKeyUp={detectar}
          onBlur={() => setMayusculas(false)}
        />
        <button
          type="button"
          aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
          aria-pressed={visible}
          onClick={() => setVisible((v) => !v)}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {mayusculas && (
        <p role="status" className="flex items-center gap-1.5 text-xs font-medium text-warning">
          <TriangleAlert className="size-3.5" /> Bloq Mayús está activado
        </p>
      )}
    </div>
  );
}
