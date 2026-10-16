import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";
import { marcarAvisadas, notificar, pendientesDeAvisar, resumenAlertas } from "@/lib/notificaciones";

const CADA_HORA = 60 * 60 * 1000;

export function useAlertas() {
  const { data } = useQuery({
    queryKey: keys.alertas,
    queryFn: api.alertas,
    refetchInterval: CADA_HORA,
  });

  useEffect(() => {
    if (!data || data.length === 0) return;
    const nuevas = pendientesDeAvisar(data);
    if (nuevas.length === 0) return;
    const { titulo, cuerpo } = resumenAlertas(nuevas);
    void notificar(titulo, cuerpo).then((enviada) => {
      if (enviada) marcarAvisadas(nuevas);
    });
  }, [data]);

  return data ?? [];
}
