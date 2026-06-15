# Reasignación masiva de estado de incidencias desde el listado

- **Fecha:** 2026-06-15
- **Autor:** Tanya Tree + Claude Opus 4.8
- **Ticket:** t1154
- **Tipo:** Funcionalidad
- **Componente:** Support — Incidencias (listado, detalle), Core (modelo Issue)
- **Impacto:** Experiencia de Usuario, Productividad del Operador, Integridad de Datos

## 🎯 Resumen

Soporte necesitaba poder cambiar el **estado** de muchas incidencias a la vez luego de filtrarlas, en lugar de editar una por una desde la vista de detalle — algo inviable cuando decenas o cientos de incidencias comparten la misma situación. Este cambio agrega una herramienta de reasignación masiva integrada en el listado existente (`list_issues`). El riesgo principal que motivó el diseño era que un operador seleccionara "todo" por accidente y reasignara incidencias que no debía, por lo que la funcionalidad combina selección explícita estilo Gmail, una confirmación obligatoria en dos pasos, una baranda de "filtro acotado" para el modo de filtro completo, y restricción de acceso por grupo. La lógica compartida de cambio de estado (`next_action_date` / `closing_date`) se extrajo a un helper del modelo para que el flujo individual y el masivo se comporten de forma idéntica.

## ✨ Cambios

### 1. Helper compartido de cambio de estado en el modelo Issue

**Archivo:** `support/models.py`

Las reglas de `next_action_date` / `closing_date` que antes vivían en línea dentro de `IssueDetailView.form_valid` se extrajeron a un método reutilizable, para que el flujo individual y el masivo apliquen la misma lógica:

```python
def apply_status_change(self, new_status):
    """Cambia el estado aplicando reglas compartidas; devuelve los campos modificados.

    - Estado nuevo terminal (slug en ISSUE_STATUS_FINISHED_LIST) sin
      closing_date -> setea closing_date a hoy.
    - Estado nuevo no terminal con next_action_date faltante/en el pasado ->
      lo setea a mañana.
    No guarda; el llamador persiste vía save()/bulk_update.
    """
```

El método devuelve la lista de campos modificados para que el llamador pueda pasarlos a `save(update_fields=...)`.

### 2. La edición individual reutiliza el helper compartido

**Archivo:** `support/views/all_views.py`

`IssueDetailView.form_valid` ahora delega los efectos posteriores al guardado a `apply_status_change`. Como consecuencia deliberada, elegir un estado terminal manualmente ahora también setea `closing_date` (antes solo se seteaba vía el camino de resolución-fuerza-resuelto) — ver Decisiones de Diseño.

### 3. Vista de reasignación masiva (dos pasos, dos modos de selección)

**Archivo:** `support/views/bulk_reassign_status.py` (nuevo)

`BulkReassignIssueStatusView` acepta un POST con un `new_status` destino y un `mode`:

- `ids`: una lista explícita de ids de incidencias marcadas.
- `filter`: el queryset filtrado completo, reconstruido del lado del servidor reproduciendo el querystring del filtro original a través de `IssueFilter` — el mismo mecanismo que usa el export a CSV, así "todo el filtro" siempre coincide con lo que vio el usuario.

El primer POST (sin `confirmed`) renderiza la pantalla de confirmación; el segundo (`confirmed=1`) aplica el cambio dentro de `transaction.atomic()`, llamando a `apply_status_change` por cada incidencia y registrando cada cambio en `LogEntry` (anterior → nuevo). El acceso está restringido a superusuarios y al grupo `Admins` mediante `UserPassesTestMixin`.

### 4. Baranda de filtro acotado para el modo de filtro completo

**Archivos:** `support/views/bulk_reassign_status.py`, `support/views/all_views.py`, `support/templates/list_issues.html`

La opción de filtro completo solo está disponible cuando el filtro tiene seleccionados **ambos**, un `status` y una `sub_category`. Esto se aplica en dos capas:

- **Backend (autoritativo):** la vista rechaza un POST en modo `filter` con un mensaje de error cuando el querystring carece de cualquiera de los dos parámetros.
- **Frontend (UX):** `IssueListView` expone un flag `filter_is_narrow`; el JS del listado solo muestra el cartel "Seleccionar todas las N que coinciden con el filtro" cuando es verdadero.

### 5. UI del listado: casillas, barra de acción, cartel estilo Gmail

**Archivo:** `support/templates/list_issues.html`

Se agregó una columna de casillas, una casilla de cabecera que marca todo (selecciona la página visible), una barra de acción con un `<select>` nativo de estado (excluido de Chosen para que mantenga ancho automático y el botón quede a su lado) y un botón "Cambiar estado", más el cartel de filtro completo. Todo el bloque está condicionado a `can_bulk_reassign`.

### 6. Pantalla de confirmación

**Archivo:** `support/templates/bulk_reassign_issue_status_confirm.html` (nuevo)

Una tarjeta AdminLTE que muestra la cantidad afectada, el estado destino, el desglose por estado actual y el rango de fechas de las incidencias (más vieja / más nueva), con botones explícitos "Confirmar y aplicar" y "Cancelar".

## 📁 Archivos Modificados

- **`support/models.py`** — Se agregó `Issue.apply_status_change`; se importó `timedelta`
- **`support/views/all_views.py`** — `IssueDetailView.form_valid` reutiliza el helper; `IssueListView.get_context_data` expone `can_bulk_reassign`, `issue_statuses`, `filter_querystring`, `filter_is_narrow`
- **`support/views/bulk_reassign_status.py`** — (nuevo) vista de reasignación masiva
- **`support/templates/list_issues.html`** — UI de selección, barra de acción, cartel de filtro completo, JS
- **`support/templates/bulk_reassign_issue_status_confirm.html`** — (nuevo) pantalla de confirmación
- **`support/urls.py`** — Ruta `bulk_reassign_issue_status`

## 📁 Archivos Creados

- **`support/views/bulk_reassign_status.py`** — `BulkReassignIssueStatusView`
- **`support/templates/bulk_reassign_issue_status_confirm.html`** — Plantilla de confirmación en dos pasos
- **`tests/test_bulk_reassign_issue_status.py`** — Suite de tests (10 tests)

## 📚 Detalles Técnicos

**Por qué `select_for_update(of=("self",))`:** el bucle de aplicación lockea las filas de incidencia mientras itera, pero `status` y `contact` son FKs nullable y un `FOR UPDATE` plano sobre sus outer joins no es soportado por PostgreSQL. Restringir el lock a la tabla Issue (`of="self"`) evita el error.

**El servidor como fuente de verdad:** en modo `filter` el conjunto afectado siempre se recalcula desde el querystring en el POST; el cliente nunca envía una cantidad final ni una lista de ids para la selección de filtro completo. El estado destino se valida contra la base de datos, nunca se confía en el POST.

**Sin signals perdidos:** los guardados tipo `bulk` saltean signals, pero `support/signals.py` está actualmente vacío, así que no se omiten efectos colaterales. (Anotado para el futuro.)

## 🧪 Pruebas Manuales

1. **Caso exitoso — reasignar algunas incidencias seleccionadas:**
   - Como Admin, abrir el listado de incidencias, filtrar, marcar 2–3 filas, elegir un estado destino, hacer clic en "Cambiar estado", confirmar.
   - **Verificar:** Solo cambian las incidencias elegidas; se crea un `LogEntry` por incidencia; un estado no terminal setea `next_action_date` a mañana.

2. **Caso exitoso — modo filtro completo con un filtro acotado:**
   - Seleccionar un `status` y una `sub_category` en el filtro, marcar la casilla de cabecera de la página, luego hacer clic en "Seleccionar todas las N que coinciden con el filtro", elegir un estado, confirmar.
   - **Verificar:** La cantidad y el rango de fechas de la confirmación coinciden con el conjunto filtrado; cambian todas las incidencias que coinciden.

3. **Caso borde — filtro completo bloqueado sin un filtro acotado:**
   - Filtrar solo por estado (sin subcategoría).
   - **Verificar:** El cartel "seleccionar todo el filtro" no aparece; un POST en modo `filter` armado a mano es rechazado con un error y nada cambia.

4. **Caso borde — un estado terminal setea closing_date:**
   - Reasignar incidencias a un estado terminal (ej. "resuelto").
   - **Verificar:** `closing_date` queda seteado a hoy para las incidencias afectadas.

5. **Caso borde — permiso denegado:**
   - Como usuario no admin, hacer POST al endpoint masivo.
   - **Verificar:** 403; el listado no renderiza la UI masiva para ese usuario.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos (solo un método nuevo del modelo, sin cambio de esquema).
- No se requieren cambios de configuración.
- El acceso depende de que exista el grupo `Admins`; los superusuarios siempre tienen acceso.

## 🎓 Decisiones de Diseño

- **Baranda en dos capas.** Ocultar el cartel de filtro completo en la UI no alcanza — la misma restricción se aplica en la vista, así el camino peligroso de "reasignar todo" no puede dispararse con una petición armada.
- **Efectos de estado unificados.** Extraer `apply_status_change` hizo que la edición individual también setee `closing_date` en estados terminales. Esto se confirmó como deseable: coincide con `mark_solved()` y con el sentido de "fecha de cierre", a costa de un cambio menor de comportamiento en el formulario individual.

## 🚀 Mejoras Futuras

- Permitir reasignar masivamente `assigned_to` o `resolution` (este ticket cubre solo `status`).
- Tope numérico opcional con confirmación reforzada por encima de N incidencias.

---

**Fecha:** 2026-06-15
**Autor:** Tanya Tree + Claude Opus 4.8
**Branch:** t1154
**Tipo de cambio:** Funcionalidad
**Módulos afectados:** Support (Incidencias), Core (modelo Issue)
