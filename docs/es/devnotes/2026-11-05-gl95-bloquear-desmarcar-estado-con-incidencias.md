# Un estado terminal con incidencias no se puede desmarcar

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#95
- **Tipo:** Mejora
- **Componente:** Support (estados de incidencia)
- **Impacto:** Integridad de datos

## 🎯 Resumen

Desmarcar «Terminal» en un estado reabría todas sus incidencias y les borraba la fecha de cierre, y volver a marcarlo les ponía a todas la fecha de ese día, así que las fechas reales sólo se podían recuperar a mano desde el historial. Una confirmación no alcanzaba como protección para algo que puede tocar decenas de miles de incidencias. Ahora el admin rechaza el desmarcado mientras el estado tenga incidencias.

## ✨ Cambios

### 1. El form del admin lo rechaza

**Archivo:** `support/forms.py`

`IssueStatusAdminForm` agrega un error en `is_terminal` cuando el estado tiene incidencias. Para desmarcarlo, primero hay que pasarlas a otro estado. Un estado sin incidencias se puede seguir desmarcando.

### 2. Se va el código que reabría incidencias

**Archivos:** `support/models.py`, `support/admin.py`

Ya nada puede llegar a él, así que `IssueStatus.sync_issues_with_terminal()` pasa a ser `close_issues()`, e `issues_to_sync_with_terminal()` pasa a ser `issues_to_close()`: sólo se ocupan de marcar. Marcar funciona como antes: cierra hoy las incidencias sin fecha de cierre, y pide confirmar si hay alguna.

## 📁 Archivos Modificados

- **`support/forms.py`** — El control, y la confirmación sólo para marcar
- **`support/models.py`** — `close_issues()` e `issues_to_close()`
- **`support/admin.py`** — Sólo cierra después de marcar
- **`locale/es/LC_MESSAGES/django.po`** — Saca los mensajes de reapertura y agrega el nuevo
- **`tests/test_issue_status_terminal.py`** — Desmarcar con y sin incidencias

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - En el admin, desmarcá «Terminal» en un estado que tiene incidencias.
   - **Verificar:** Un error dice que primero hay que pasarlas a otro estado, y no cambia nada.

2. **Caso borde, sin incidencias:**
   - Desmarcá «Terminal» en un estado sin incidencias.
   - **Verificar:** Se guarda.

## 📝 Notas de Despliegue

No se requieren migraciones.

---

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl95-bloquear-desmarcar-estado
- **Tipo:** Mejora
- **Módulos afectados:** support
