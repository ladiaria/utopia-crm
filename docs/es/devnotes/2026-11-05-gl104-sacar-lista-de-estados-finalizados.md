# La lista vieja de estados de cierre sale de los settings

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#104
- **Tipo:** Refactorización
- **Componente:** Settings, Support
- **Impacto:** Ninguno para las instalaciones que ya aplicaron `support/0044`

## 🎯 Resumen

Si un estado es terminal lo dice `IssueStatus.is_terminal`, que se maneja desde el admin. `ISSUE_STATUS_FINISHED_LIST` estaba marcada como obsoleta y sólo la leía la migración `support/0044`. Sale de `settings.py`, y la migración conserva su valor por defecto para que una instalación que todavía no migró no pierda sus estados de cierre.

## ✨ Cambios

### 1. Se va el setting

**Archivo:** `settings.py`

Saca `ISSUE_STATUS_FINISHED_LIST` y su comentario.

### 2. La migración conserva el valor por defecto

**Archivo:** `support/migrations/0044_issuestatus_is_terminal.py`

```python
DEFAULT_FINISHED_LIST = ["solved", "not-solved"]
finished_list = getattr(settings, "ISSUE_STATUS_FINISHED_LIST", DEFAULT_FINISHED_LIST) or []
```

Una instalación que define la lista en su `local_settings.py` sigue usando la suya. Editar una migración aplicada acá es seguro: sólo cambia el valor por defecto de un paso de datos, y una instalación que ya la aplicó no la vuelve a correr.

## 📁 Archivos Modificados

- **`settings.py`** — El setting
- **`support/migrations/0044_issuestatus_is_terminal.py`** — El valor por defecto
- **`tests/test_issue_status_terminal.py`** — La migración sin el setting

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - Correr `python manage.py check` en una instalación que ya aplicó `support/0044`.
   - **Verificar:** No hay problemas, y los estados terminales del admin no cambian.

2. **Caso borde, sin migrar todavía:**
   - En una base anterior a `support/0044`, con los estados `solved` y `not-solved` y sin la lista en `local_settings.py`, correr `migrate`.
   - **Verificar:** Los dos estados quedan terminales.

## 📝 Notas de Despliegue

No hay migraciones nuevas. Una vez aplicada `support/0044`, la lista puede quedar en un `local_settings.py` sin ningún efecto.

---

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl104-sacar-finished-list
- **Tipo:** Refactorización
- **Módulos afectados:** settings, support
