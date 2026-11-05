# La fecha de cierre de una incidencia siempre acompaña al estado

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#99
- **Tipo:** Corrección de error
- **Componente:** Support (incidencias)
- **Impacto:** Integridad de datos, consola de comunidad

## 🎯 Resumen

Convivían dos ideas de «cerrada»: casi todo el sistema mira si el estado es terminal, mientras que la consola de comunidad además exigía la fecha de cierre vacía. Cada camino que cerraba una incidencia escribía la fecha por su cuenta, y reabrirla la dejaba puesta, así que una incidencia abierta podía quedar oculta en la consola. Ahora `Issue.save()` mantiene la regla en un solo lugar, y si una incidencia está cerrada lo decide sólo `IssueStatus.is_terminal`.

## ✨ Cambios

### 1. La regla vive en `Issue.save()`

**Archivo:** `support/models.py`

- Pasar a un estado terminal pone la fecha de hoy, salvo que la incidencia ya tenga una.
- Pasar de un terminal a otro conserva la fecha.
- Pasar a cualquier otro estado, desde donde sea, borra la fecha.

```python
if self.has_terminal_status():
    self.closing_date = self.closing_date or date.today()
else:
    self.closing_date = None
```

La regla no necesita el estado anterior. Cuando `update_fields` incluye `status`, se le suma `closing_date`, porque la reasignación masiva guarda así. Por eso tampoco es un signal `pre_save`: un signal no puede sumar un campo a `update_fields`.

`bulk_update` y `queryset.update()` no llaman a `save()`. El único que cambia estados es `IssueStatus.sync_issues_with_terminal()`, que ya maneja la fecha.

### 2. Los caminos que escribían la fecha por su cuenta

**Archivos:** `support/models.py`, `support/views/all_views.py`

- `apply_status_change()` sólo se ocupa de `next_action_date`.
- `mark_solved()` ya no pisa la fecha de una incidencia que estaba cerrada.
- `IssueDetailView` ya no pone la fecha cuando una resolución resuelve la incidencia automáticamente.
- `NewIssueView`, que creaba incidencias en estado terminal sin fecha, queda cubierta por la regla.

### 3. La consola de comunidad decide por el estado

**Archivo:** `support/views/all_views.py`

`CommunityConsoleView`, `CommunityManagerDashboardView`, `CommunityManagerAssignView` y `CommunityManagerOverviewView` sacan `closing_date__isnull=True` y conservan la exclusión por `is_terminal`.

## 📁 Archivos Modificados

- **`support/models.py`** — `Issue.save()`, y `apply_status_change()` y `mark_solved()` sin la fecha
- **`support/views/all_views.py`** — Filtros de la consola de comunidad y la resolución automática de `IssueDetailView`
- **`support/views/bulk_reassign_status.py`** — Comentario
- **`tests/test_issue_status_terminal.py`** — La incidencia abierta con fecha ahora se arma con `update()`
- **`tests/test_issue_terminal_status_badge.py`** — Saca el caso de un estado terminal sin fecha, que ya no existe

## 📁 Archivos Creados

- **`tests/test_issue_closing_date.py`** — La regla a través de `save()`, `update_fields`, `mark_solved()` y la pantalla de la incidencia

## 🧪 Pruebas Manuales

1. **Reabrir y volver a cerrar:**
   - Pasá una incidencia abierta a un estado terminal desde su pantalla.
   - **Verificar:** Tiene la fecha de hoy.
   - Pasala a un estado no terminal.
   - **Verificar:** No tiene fecha de cierre, y aparece en la consola de comunidad si está asignada.
   - Volvé a pasarla a un estado terminal.
   - **Verificar:** Tiene la fecha de ese día, no la primera.

2. **Caso borde, entre terminales:**
   - Tomá una incidencia cerrada con una fecha vieja y pasala a otro estado terminal.
   - **Verificar:** La fecha no cambia.

3. **Caso borde, creada cerrada:**
   - Creá una incidencia nueva directamente en un estado terminal.
   - **Verificar:** Tiene la fecha de hoy.

## 📝 Notas de Despliegue

- No se requieren migraciones.
- **Normalizar los datos antes.** Si no, el próximo guardado de una incidencia terminal vieja sin fecha le pone la de hoy, y el próximo guardado de una incidencia abierta con fecha se la borra. la diaria lo hace con un script de un solo uso en su paquete privado, que corre antes y después del deploy.

## 🎓 Decisiones de Diseño

- **`save()` en vez de un signal:** el modelo es de este repo, así que un signal no agrega nada y además no podría escribir a través de `update_fields`.
- **Sin estado anterior:** la regla depende sólo del estado actual. Eso la hace simple, y es la razón por la que los datos tienen que estar parejos antes de que rija.

---

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl99-fecha-cierre-regla
- **Tipo:** Corrección de error
- **Módulos afectados:** support
