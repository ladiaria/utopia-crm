# Los estados terminales de incidencia se manejan desde el admin, y los slugs ya no cambian al renombrar

- **Fecha:** 2026-11-04
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl87-estados-terminales (it/utopia-crm-ladiaria#87, #81)
- **Tipo:** Mejora
- **Componente:** Support (incidencias), Core Models, Logistics
- **Impacto:** Operación, integridad de datos

## 🎯 Resumen

Que un estado de incidencia fuera terminal (de cierre) era una lista de slugs en `local_settings.py`,
`ISSUE_STATUS_FINISHED_LIST`, distinta en cada servidor. Hacer terminal un estado implicaba editar la configuración de
cada servidor y completar a mano la fecha de cierre de las incidencias que ya estaban en ese estado. Ahora es un booleano
del estado, `IssueStatus.is_terminal`, que se maneja desde el admin con un permiso propio. Va junto con otro arreglo,
porque manejar los estados desde el admin hace más probable renombrarlos: renombrar un estado o una subcategoría le
rearmaba el slug, y eso rompía sin aviso todo lo que lo busca por slug. Ahora el slug se arma sólo al crearlos.

## ✨ Cambios

### 1. `IssueStatus.is_terminal` reemplaza a la lista

**Archivos:** `support/models.py`, `core/models.py`, `support/filters.py`, `support/forms.py`, `logistics/views.py`,
`support/views/all_views.py`, `support/views/seller_console.py`, `support/management/commands/close_invoicing_issues.py`

Todo lo que leía la lista ahora lee el booleano:

```python
# Antes
Issue.objects.exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
# Después
Issue.objects.exclude(status__is_terminal=True)
```

`Issue.has_terminal_status()` e `Issue.apply_status_change()` también lo usan. Se sacan las guardas de `seller_console.py`
para instalaciones sin la lista: con el booleano no hay caso «sin configurar».

### 2. Un permiso propio para cambiarlo

**Archivo:** `support/admin.py`

`support.change_issuestatus_terminal` es aparte del permiso de editar un estado. Sin él, `is_terminal` es de sólo lectura,
también al crear un estado, así que un estado nuevo no es terminal. `is_terminal` se ve y se puede filtrar en la lista,
pero no es `list_editable`: editarlo ahí se saltearía los controles de abajo.

### 3. Los estados de los que dependen los settings no pueden cambiar de lado

**Archivo:** `support/forms.py` (`IssueStatusAdminForm`)

Se controla sólo cuando cambia `is_terminal`, así que esos estados se pueden renombrar:

- `ISSUE_STATUS_SOLVED` e `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE` no se pueden desmarcar: los cierres automáticos pasan
  incidencias a esos estados para cerrarlas.
- `ISSUE_STATUS_NEW`, `ISSUE_STATUS_ASSIGNED`, `ISSUE_STATUS_UNASSIGNED` e `ISSUE_STATUS_PENDING` no se pueden marcar: el
  CRM se los pone a incidencias que siguen abiertas.

### 4. Cambiar el booleano arrastra a las incidencias del estado

**Archivos:** `support/models.py` (`IssueStatus.sync_issues_with_terminal`), `support/forms.py`, `support/admin.py`

`apply_status_change` actúa cuando una incidencia cambia de estado, no cuando cambia el estado mismo. Por eso, si el estado
tiene incidencias, el formulario pide confirmar con el número, y al guardar se les aplican las mismas reglas:

- **A terminal:** las que no tienen fecha de cierre reciben la de hoy.
- **A no terminal:** todas pierden la fecha de cierre, y reciben mañana como fecha de próxima acción si no la tienen o ya
  pasó.

Usa `bulk_update_with_history`, así que el historial de cada incidencia dice quién la cerró o reabrió y por qué, sin un
`save()` por fila. El `LogEntry` del admin del estado registra a cuántas incidencias afectó.

### 5. Slugs fijos al crear, y nombres únicos en el admin

**Archivos:** `support/models.py`, `support/forms.py` (`UniqueNameAdminFormMixin`, `IssueSubcategoryAdminForm`), `support/admin.py`

`IssueStatus.slug` e `IssueSubcategory.slug` pasan a `always_update=False`. `AutoSlugField` no los hace únicos, y un segundo
«Resuelto» rompería todos los `IssueStatus.objects.get(slug=...)`. Por eso los dos admins rechazan un nombre nuevo o
cambiado que ya esté en uso, o que sólo se diferencie de uno en uso en mayúsculas, tildes o signos (es decir, el mismo
slug). Guardar sin cambiar el nombre no se controla.

### 6. La migración carga el booleano desde la lista de cada instalación

**Archivos:** `support/migrations/0044_issuestatus_is_terminal.py`, `settings.py`

Agrega el campo y el permiso, altera los dos slugs (sólo de estado: no toca columnas ni datos) y marca como terminales los
estados de `ISSUE_STATUS_FINISHED_LIST`, con los settings del servidor donde corre. La lista queda marcada como obsoleta en
`settings.py`: sólo la lee esta migración.

## 📁 Archivos Modificados

- **`support/models.py`** — `is_terminal`, el permiso, los slugs fijos, `issues_to_sync_with_terminal()` y
  `sync_issues_with_terminal()`.
- **`support/forms.py`** — `IssueStatusAdminForm`, `IssueSubcategoryAdminForm`, `UniqueNameAdminFormMixin`; el bloqueo por
  «no entregado» lee el booleano.
- **`support/admin.py`** — `IssueStatusAdmin` e `IssueSubcategoryAdmin` con los formularios nuevos; sólo lectura sin el
  permiso; registro y mensaje con el número de incidencias.
- **`core/models.py`**, **`logistics/views.py`**, **`support/filters.py`**, **`support/views/all_views.py`**,
  **`support/views/seller_console.py`**, **`support/management/commands/close_invoicing_issues.py`** — Leen el booleano.
- **`settings.py`** — `ISSUE_STATUS_FINISHED_LIST` marcada como obsoleta.
- **`locale/es/LC_MESSAGES/django.po`** — Traducciones al español.
- **`tests/test_bulk_reassign_issue_status.py`**, **`tests/test_close_invoicing_issues.py`**,
  **`tests/test_issue_resolution_auto_solved.py`**, **`tests/test_issue_terminal_status_badge.py`**,
  **`tests/test_new_issue_not_delivered_block.py`**, **`tests/test_seller_console_never_paid.py`** — Crean los estados
  terminales con `is_terminal=True`.
- **`CHANGELOG.md`** — Entrada.

## 📁 Archivos Creados

- **`support/migrations/0044_issuestatus_is_terminal.py`** — Campo, permiso, slugs y carga inicial.
- **`tests/test_issue_status_terminal.py`** — 19 tests: la carga inicial, renombrar conserva el slug, el permiso, los
  controles sobre los estados de los settings, la confirmación, el cierre y la reapertura, los nombres únicos, y que las
  incidencias sin estado cuentan como abiertas.

## 📚 Detalles Técnicos

- **Las incidencias sin estado siguen contando como abiertas:** `exclude(status__is_terminal=True)` las conserva, igual que
  el viejo `exclude(status__slug__in=...)`. Hay un test.
- **Medido sobre una copia de los datos de producción:** reabrir un estado con 39.644 incidencias tarda 13,5 segundos,
  dentro de la transacción del admin. Si falla, no queda nada a medias.
- **Revertir la migración** borra la columna y no toca la lista, así que el código viejo sigue andando con ella si la lista
  sigue en los settings.
- **Tests automatizados:** pasa la suite completa sin `test_cmssync` (418 tests).

## 🧪 Pruebas Manuales

1. **Marcar un estado con incidencias (caso exitoso):**
   - Con el permiso, en el admin, abrir un estado no terminal que tenga incidencias abiertas, marcar «Terminal» y guardar.
   - **Verificar:** un error pide confirmar, con el número de incidencias. Al marcar la casilla de confirmación y guardar de
     nuevo, las incidencias tienen la fecha de cierre de hoy, salen de las listas de abiertas y su historial muestra tu
     usuario.

2. **Desmarcarlo:**
   - En el mismo estado, desmarcar «Terminal», confirmar y guardar.
   - **Verificar:** las incidencias no tienen fecha de cierre, vuelven a las listas de abiertas, y las que no tenían fecha
     de próxima acción, o la tenían pasada, tienen la de mañana.

3. **Sin el permiso (caso borde):**
   - Con un usuario que puede editar estados pero no tiene el permiso nuevo, abrir un estado.
   - **Verificar:** «Terminal» se ve pero no se puede cambiar, y no aparece la casilla de confirmación.

4. **Estados de los que dependen los settings (caso borde):**
   - Intentar desmarcar el estado de `ISSUE_STATUS_SOLVED` y marcar el de `ISSUE_STATUS_NEW`.
   - **Verificar:** los dos se rechazan con un error en el campo. Renombrarlos funciona.

5. **Renombrar y repetir un nombre (caso borde):**
   - Renombrar un estado y después intentar crear otro con ese nombre, escrito con otras mayúsculas o tildes.
   - **Verificar:** el slug del renombrado no cambió, y el nuevo se rechaza.

## 📝 Notas de Despliegue

- **Se requiere migración:** `support/0044_issuestatus_is_terminal`.
- **`ISSUE_STATUS_FINISHED_LIST` tiene que seguir en `local_settings.py` cuando corre `migrate`**, o no se marca ningún
  estado. Después se puede sacar de ahí.
- **Correr `migrate` enseguida después de deployar el código:** hasta entonces, las pantallas que filtran incidencias
  responden 500, porque la columna todavía no existe.
- **Un paquete de customización que lea la lista** puede seguir haciéndolo hasta que esto esté migrado, y después tiene que
  pasar al campo: la lista ya no dice qué es terminal. El de la diaria lo hace en it/utopia-crm-ladiaria!211, deployado
  después de este.
- **Dar el permiso** «Puede cambiar si un estado de incidencia es terminal» a quien corresponda. Los superusuarios ya lo
  tienen.

## 🎓 Decisiones de Diseño

- **La lista no queda como respaldo en tiempo de ejecución:** con un `OR` entre el booleano y la lista, desmarcar un estado
  en el admin no tendría efecto. Queda sólo como carga inicial de la migración.
- **Controles en el formulario, no un check de sistema:** un check que consulta la base corre antes de `migrate`, y fallaría
  por la columna que todavía no existe.
- **Sin `HistoricalRecords` en `IssueStatus`:** el `LogEntry` ya registra quién cambió el booleano, cuándo y a cuántas
  incidencias afectó. Sería otra tabla para lo mismo.
- **Nombres únicos en el formulario, no en la base:** alcanza para el admin, que es donde se crean los estados, y no
  necesita revisar los datos existentes. Un estado creado desde un shell o un fixture todavía podría repetir un slug.

## 🚀 Mejoras Futuras

- Decidir si desmarcar un estado con incidencias se bloquea en vez de confirmarse (it/utopia-crm-ladiaria#95).
- Sacar `ISSUE_STATUS_FINISHED_LIST` de `settings.py` cuando ninguna instalación la necesite para migrar.
- `unique=True` en los dos slugs, para cubrir lo que el formulario no cubre.
- `get_finished_issues_by_subcategory_count()` y `get_finished_issues_by_category_count()` de `core/models.py` usan
  `exclude`, así que devuelven las abiertas: este cambio mantuvo ese comportamiento.

---

- **Fecha:** 2026-11-04
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl87-estados-terminales
- **Tipo de cambio:** Mejora
- **Módulos afectados:** Support, Core, Logistics
