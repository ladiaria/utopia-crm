# Registro de Asistencia de Vendedores del Call Center

- **Fecha:** 2026-04-29
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1132
- **Tipo:** Funcionalidad
- **Componente:** Support — Vendedores, Administración de Campañas
- **Impacto:** Flujo de Operadores, Seguimiento de RRHH, Cálculos Futuros de Comisiones

## 🎯 Resumen

Los responsables del call center necesitaban registrar la asistencia e inasistencia diaria de los vendedores que trabajan en el call center, para alimentar estadísticas futuras y ajustar la cantidad de días laborables computables de cada vendedor (las inasistencias justificadas reducen el objetivo esperado). Este ticket introduce cuatro modelos nuevos (`Shift`, `AbsenceReason`, `AttendanceRecord`, `SellerAttendance`), dos campos nuevos en `Seller`, una vista dedicada accesible desde el menú de Campaign Management, y una suite completa de tests unitarios. También agrega documentación exhaustiva a `BreadcrumbsMixin` para clarificar una interacción sutil entre `@cached_property`, métodos simples y la resolución de callables en los templates de Django.

## ✨ Cambios

### 1. Modelo `Shift` y nuevos campos en `Seller`

**Archivo:** `support/models.py`

El nuevo modelo `Shift` almacena turnos de trabajo con nombre y horarios de inicio y fin configurables, editables desde el admin de Django sin necesidad de un deploy. Dos turnos por defecto son sembrados vía fixture: Matutino (09:00–17:00) y Vespertino (17:00–21:00).

Se agregaron dos campos a `Seller`:

- `call_center` (`BooleanField`, default `False`) — marca los vendedores sujetos al control de asistencia.
- `shift` (`ForeignKey` a `Shift`, nullable) — el turno asignado al vendedor; se usa para preinicializar los inputs de hora en la vista de asistencia.

### 2. Modelos `AbsenceReason`, `AttendanceRecord` y `SellerAttendance`

**Archivo:** `support/models.py`

`AbsenceReason` almacena categorías de inasistencia configurables. Cada motivo se marca como justificado o injustificado (esta distinción impulsará la lógica de comisiones futura). Su `__str__` agrega la etiqueta de justificación entre paréntesis para que los operadores siempre la vean de un vistazo. La FK desde `SellerAttendance` hacia `AbsenceReason` usa `on_delete=PROTECT`, lo que impide eliminar un motivo que tenga registros asociados — el admin muestra el error automáticamente.

`AttendanceRecord` es un encabezado identificado por fecha (`unique=True`). `SellerAttendance` almacena una fila por vendedor por día (`unique_together`) con estado (Presente / Ausente), un motivo de inasistencia opcional, y los horarios reales de inicio y fin del turno (que pueden diferir de los valores por defecto del turno asignado).

### 3. Registros en el admin y mejoras a `SellerAdmin`

**Archivo:** `support/admin.py`

Los cuatro modelos nuevos se registran siguiendo el patrón existente con `@admin.register`. `SellerAdmin` fue mejorado con `list_filter` en `internal`, `call_center` y `shift`; `search_fields` en nombre y nombre de usuario; y `call_center` y `shift` agregados a `list_display`.

### 4. `SellerAttendanceView`

**Archivo:** `support/views/all_views.py`

Vista basada en clase (`LoginRequiredMixin + UserPassesTestMixin + BreadcrumbsMixin + TemplateView`) en `/seller_attendance/`.

- **GET:** lee el parámetro `date` de la query (por defecto hoy), carga todos los vendedores con `call_center=True`, busca cualquier `AttendanceRecord` existente para esa fecha, y construye una fila por vendedor preinicializada con el estado guardado o los valores por defecto del turno.
- **POST:** restringido a superusuarios y usuarios con el permiso `support.change_sellerattendance`. Las filas donde el estado queda en blanco se omiten (los operadores pueden registrar asistencia en varios momentos del día). Valida que las filas con inasistencia tengan un motivo y que todas las filas guardadas tengan horarios de turno. Usa `update_or_create` en `SellerAttendance` para que los guardados repetidos en la misma fecha sean seguros.

Los vendedores sin turno asignado muestran un badge de advertencia en línea y no pueden guardarse hasta que el turno sea configurado en el admin.

La vista llama a `self.get_context_data()` (que ejecuta la inyección de `BreadcrumbsMixin`) y fusiona las claves específicas de la vista en él, haciendo que los breadcrumbs funcionen correctamente aunque `get` y `post` usen `render()` directamente en lugar de delegar a `TemplateView.get`.

### 5. Template `seller_attendance.html`

**Archivo:** `support/templates/support/seller_attendance.html`

Card de AdminLTE con un selector de fecha HTML5 (`<input type="date">`) que dispara un GET al cambiar. Las columnas de la tabla de asistencia son: Vendedor, Estado (select), Motivo de Inasistencia (select, habilitado solo cuando se elige Ausente), Inicio de Turno (input de hora), Fin de Turno (input de hora). Los inputs de turno se ocultan con `display:none` en línea cuando el estado está en blanco.

El JavaScript en `{% block extra_js %}` conecta los selects de estado al cargar y al cambiar, y realiza validación en el cliente antes de enviar (horarios de turno faltantes, ausente sin motivo) para dar feedback inmediato sin un viaje al servidor.

Los mensajes son renderizados exclusivamente por el bloque `{% block messages %}` del template base — no hay bloque duplicado en este template.

### 6. Ítem de menú en el sidebar

**Archivo:** `templates/components/sidebar_items/_campaign_management.html`

"Seller Attendance" agregado antes del hook `{% include_if_exists %}`, siguiendo el patrón existente de `{% url ... as ... %}` para detección del enlace activo.

### 7. Fixture y URL

**Archivos:** `support/fixtures/shifts.json`, `support/urls.py`

Los dos turnos por defecto se proveen como fixture cargable con `manage.py loaddata`. La URL `seller_attendance/` está registrada bajo la app `support` con el nombre `seller_attendance`.

### 8. Tests unitarios

**Archivo:** `tests/test_seller_attendance.py`

14 tests que cubren: `AbsenceReason.__str__` (etiquetas justificado/injustificado), unicidad de fecha en `AttendanceRecord`, prevención de eliminación con `PROTECT`, GET con y sin datos previos, filtro de solo call center, casos exitosos de POST presente/ausente, fallos de validación en POST (ausente sin motivo, horarios de turno faltantes, POST de no-admin → 403, sin motivos activos), y seguridad del upsert.

### 9. Documentación de `BreadcrumbsMixin`

**Archivo:** `core/mixins.py`

Se agregó un docstring completo que explica: cómo definir breadcrumbs en una subclase, por qué `@cached_property` y un método simple funcionan igual (Django templates llaman los callables automáticamente), y el patrón explícito necesario cuando `get`/`post` omiten `get_context_data`.

## 📁 Archivos Modificados

- **`support/models.py`** — Agregado modelo `Shift`; agregados campos `call_center` y `shift` a `Seller`; agregados modelos `AbsenceReason`, `AttendanceRecord`, `SellerAttendance` con constantes
- **`support/admin.py`** — Mejorado `SellerAdmin`; registrados `Shift`, `AbsenceReason`, `AttendanceRecord`, `SellerAttendance`
- **`support/views/all_views.py`** — Agregada `SellerAttendanceView` y sus imports de modelos
- **`support/urls.py`** — Registrada URL `seller_attendance/` e importada `SellerAttendanceView`
- **`templates/components/sidebar_items/_campaign_management.html`** — Agregado ítem de menú "Seller Attendance"
- **`core/mixins.py`** — Agregado docstring completo a `BreadcrumbsMixin`
- **`templates/components/_footer.html`** — Versión actualizada a 0.5.1
- **`locale/es/LC_MESSAGES/django.po`** — Nuevas cadenas extraídas y compiladas

## 📁 Archivos Creados

- **`support/migrations/0040_absencereason_attendancerecord_shift_and_more.py`** — Migración para todos los modelos y campos nuevos
- **`support/fixtures/shifts.json`** — Turnos por defecto: Matutino y Vespertino
- **`support/templates/support/seller_attendance.html`** — Template de la vista de asistencia
- **`tests/test_seller_attendance.py`** — 14 tests unitarios

## 📚 Detalles Técnicos

- `SellerAttendance.absence_reason` usa `on_delete=PROTECT`. Intentar eliminar un `AbsenceReason` que tenga filas de asistencia asociadas lanza un `ProtectedError` de Django, que el admin muestra como un error amigable para el usuario. No se requiere lógica personalizada.
- El control de permisos en `post` usa `request.user.is_superuser or request.user.has_perm("support.change_sellerattendance")`. Los usuarios solo-staff (que pasan `test_func`) pueden hacer GET pero no POST, dando acceso de solo lectura a los managers sin otorgar derechos de edición.
- Los horarios de turno en `SellerAttendance` se almacenan independientemente de `Seller.shift` — la FK del turno solo provee valores por defecto. Los operadores pueden ajustar los horarios reales por día (por ejemplo, si un vendedor llegó tarde), y esos horarios son los que se persisten.
- El segundo elemento del retorno de `get_or_create` se nombró `_created` para evitar sombrear el alias `_` de `gettext_lazy`, lo que causaría un `UnboundLocalError` cuando el compilador de bytecode de Python detecta la asignación local.

## 🧪 Pruebas Manuales

1. **Caso exitoso — registrar asistencia de un vendedor presente:**
   - Marcar un `Seller` como `call_center=True` y asignarle un `Shift` en el admin.
   - Crear al menos un `AbsenceReason` activo.
   - Navegar a `/seller_attendance/` como superusuario.
   - Seleccionar la fecha de hoy; el vendedor aparece con los horarios del turno preinicializados.
   - Establecer estado en "Present" y hacer clic en "Save attendance".
   - **Verificar:** La página redirige, el mensaje de éxito aparece una sola vez (solo en la parte superior), y recargar la misma fecha muestra "Present" preseleccionado.

2. **Caso exitoso — registrar una inasistencia con motivo:**
   - Establecer el estado del vendedor en "Absent"; el select de motivo de inasistencia se habilita.
   - Elegir un motivo y guardar.
   - **Verificar:** Existe una fila `SellerAttendance` con `status="A"` y el `absence_reason` correcto.

3. **Caso exitoso — manager (staff, no superusuario) solo puede consultar:**
   - Iniciar sesión como usuario staff sin el permiso `change_sellerattendance`.
   - Navegar a `/seller_attendance/`.
   - **Verificar:** La página carga (200), los campos de estado y turno son de solo lectura, no se muestra el botón "Save attendance".

4. **Caso borde — ausente sin motivo es rechazado:**
   - Seleccionar "Absent" pero dejar el motivo en blanco y enviar.
   - **Verificar:** El formulario se vuelve a renderizar con un mensaje de error; no se crea ninguna fila `SellerAttendance`.

5. **Caso borde — vendedor sin turno muestra advertencia:**
   - Dejar el `shift` de un vendedor en null en el admin.
   - Cargar la vista de asistencia.
   - **Verificar:** La fila del vendedor muestra un badge amarillo "No shift"; los inputs de esa fila están deshabilitados.

6. **Caso borde — guardar dos veces en la misma fecha actualiza, no duplica:**
   - Guardar asistencia para una fecha marcando un vendedor como Presente.
   - Volver a la misma fecha, cambiar el vendedor a Ausente con un motivo, y guardar de nuevo.
   - **Verificar:** `SellerAttendance.objects.filter(seller=seller, record__date=date).count()` es 1 y `status="A"`.

7. **Caso borde — eliminar un motivo de inasistencia en uso es bloqueado:**
   - En el admin, intentar eliminar un `AbsenceReason` que tenga filas `SellerAttendance` vinculadas.
   - **Verificar:** Django muestra un error "Cannot delete" listando los objetos protegidos.

## 📝 Notas de Despliegue

- **Migración requerida:** `support/0040_absencereason_attendancerecord_shift_and_more`
- Luego de migrar, cargar los turnos por defecto:

  ```bash
  python manage.py loaddata support/fixtures/shifts.json
  ```

- Luego de cargar, ir al admin y marcar los `Seller` correspondientes con `call_center=True` y asignarles un `Shift`.
- Crear al menos un `AbsenceReason` antes de que los operadores comiencen a usar la vista — la vista bloquea el guardado si no existe ninguno.
- No se requieren nuevas configuraciones.

## 🎓 Decisiones de Diseño

`Shift` se implementó como modelo (en lugar de constantes hardcodeadas o settings) para que los administradores puedan ajustar los horarios de los turnos sin un deploy. Dos turnos por defecto son sembrados vía fixture; agregar más se hace desde el admin.

La separación encabezado/detalle (`AttendanceRecord` + `SellerAttendance`) mantiene la unicidad de fecha en el nivel del registro y facilita consultar "todas las inasistencias para una fecha dada" o "todas las inasistencias de un vendedor dado" de forma eficiente, y sienta las bases para estadísticas agregadas futuras.

Las filas con estado en blanco se omiten silenciosamente al guardar en lugar de lanzar un error de validación, porque los operadores pueden acceder a la herramienta varias veces durante el día (por ejemplo, el supervisor de la mañana completa las llegadas tempranas y el de la tarde completa el resto). Obligar a completar todas las filas antes de guardar haría imposible el uso incremental.

## 🚀 Mejoras Futuras

- Agregar informes de inasistencias por rango de fechas y por vendedor (total de inasistencias, desglose justificadas vs. injustificadas) para usar en cálculos de comisiones y rendimiento.
- Exponer un flujo de importación masiva (CSV) para carga retroactiva de datos de inasistencia.
- Usar las inasistencias justificadas para reducir automáticamente la cantidad de días laborables objetivo de cada vendedor en la vista de estadísticas de rendimiento.

---

**Fecha:** 2026-04-29
**Autor:** Tanya Tree + Claude Sonnet 4.6
**Branch:** t1132
**Tipo de cambio:** Funcionalidad
**Módulos afectados:** Support, Core
