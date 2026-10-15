# Checklist de revisión (Opus)
- [ ] Cumple el contrato `docs/api.md` (nombres, tipos y códigos de error).
- [ ] Sin comentarios innecesarios; el código se entiende solo.
- [ ] Selectores solo en `backend/core/selectors.py`.
- [ ] Credenciales solo en keyring; nada sensible en logs.
- [ ] No hay login automático a Google; las pausas humanas están en el flujo de Gemini.
- [ ] La entrega exige confirmación salvo "entregar sin revisar".
- [ ] Errores manejados y reportados en Job/HTTP; sin excepciones silenciadas.
- [ ] Lint y tests en verde; pruebas nuevas para la lógica nueva.
- [ ] La UI no se bloquea (trabajo largo en Jobs) y los textos están en español.
