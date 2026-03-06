# Renovación de Consola de Vendedor: Botón "No Encontrado" y Reorganización de Diseño

**Fecha:** 2026-02-27
**Tipo:** Mejora de Funcionalidad, Mejora de UI
**Componente:** Consola de Vendedor, Gestión de Campañas
**Impacto:** Flujo de Trabajo del Vendedor, Seguimiento de Campañas
**Tarea:** t1037

## Resumen

Se renovó la consola de vendedor con un nuevo botón "No encontrado" y se reorganizó la disposición de botones. El nuevo botón permite a los vendedores marcar contactos que no pudieron localizar, avanzando al siguiente contacto mientras mantiene el contacto marcado en la campaña para reintento. Los contactos previamente marcados como "No encontrado" o "Llamar más tarde" se distinguen visualmente con badges de colores e indicadores en la lista de contactos, dando a los vendedores contexto inmediato sobre el historial de cada contacto.

## Motivación

Los vendedores necesitaban una forma de indicar que un contacto no fue encontrado/inalcanzable sin sacarlo de la campaña. Anteriormente, las únicas opciones eran:

1. **"Llamar más tarde"** — marca como "llamar después" pero no distingue semánticamente entre "llamaré después" y "no lo encontré"
2. **"No contactable"** / **"Cerrar sin contacto"** — estas opciones terminan la campaña para el contacto completamente

El cliente solicitó: *"No encontrado (se pasa al próximo cliente y se marca con un color diferente)"* — un botón que avanza al siguiente contacto y marca visualmente al actual con un color diferente.

Además, la disposición de botones se reorganizó según solicitud del cliente: botones rojos (rechazados) a la izquierda, amarillos (pendientes) en el medio, y verdes (éxito) a la derecha.

## Implementación

### 1. Nuevo Tipo de Acción `NOT_FOUND`

**Archivo:** `support/models.py`

Se agregó un nuevo tipo de acción a `SellerConsoleAction.ACTION_TYPES`:

```python
class ACTION_TYPES(models.TextChoices):
    SUCCESS = "S", _("Success")
    DECLINED = "D", _("Declined")
    PENDING = "P", _("Pending")
    NO_CONTACT = "N", _("No contact")
    SCHEDULED = "C", _("Scheduled")
    CALL_LATER = "L", _("Call later")
    NOT_FOUND = "F", _("Not found")  # Nuevo
```

### 2. Nuevo Código de Resolución de Campaña

**Archivo:** `core/choices.py`

Se agregó `NF` (No encontrado) a `CAMPAIGN_RESOLUTION_CHOICES`:

```python
("NF", _("Not found")),
```

Esto es distinto de `UN` (No se puede encontrar contacto) que termina la campaña. `NF` mantiene al contacto en la campaña para reintento.

### 3. Actualización del Comando de Gestión

**Archivo:** `core/management/commands/populate_seller_console_actions.py`

Se agregó la nueva acción a la tupla `action_types_and_names`:

| Acción | Slug | Estado de Campaña | Resolución |
| -------- | ------ | ------------------- | ------------ |
| No encontrado | `not-found` | CALLED_COULD_NOT_CONTACT (3) | NF |

**Decisión de diseño clave:** Usa `CALLED_COULD_NOT_CONTACT` (estado 3) — el mismo estado que "llamar más tarde". Esto asegura que el contacto permanezca en la cola de la campaña porque `get_not_contacted()` filtra por `status__in=[1, 3]`.

### 4. Incremento de Offset para NOT_FOUND

**Archivo:** `support/views/seller_console.py`

Se actualizó `handle_post_request` para avanzar al siguiente contacto en acciones NOT_FOUND, junto con CALL_LATER:

```python
if seller_console_action.action_type in (
    SellerConsoleAction.ACTION_TYPES.CALL_LATER,
    SellerConsoleAction.ACTION_TYPES.NOT_FOUND,
):
    offset = int(offset) + 1
```

### 5. Fecha/Hora de Última Acción en Contexto

**Archivo:** `support/views/seller_console.py`

Se agregó `last_action_datetime` al contexto de la plantilla consultando la Actividad más reciente que coincida con la última acción de consola del contacto. Esto proporciona la fecha y hora exacta de cuándo se realizó la acción "No encontrado" o "Llamar más tarde":

```python
last_action_datetime = None
if hasattr(console_instance, 'last_console_action') and console_instance.last_console_action:
    last_action_activity = Activity.objects.filter(
        contact=contact,
        campaign=campaign,
        seller_console_action=console_instance.last_console_action,
    ).order_by('-datetime').first()
    if last_action_activity:
        last_action_datetime = last_action_activity.datetime
```

### 6. Consulta Optimizada con `select_related`

**Archivo:** `support/views/seller_console.py`

Se agregó `select_related('last_console_action')` a `get_console_instances` para la categoría "new" para evitar consultas N+1 al renderizar la lista de contactos con diferenciación de colores.

### 7. Reorganización de Plantilla e Indicadores Visuales

**Archivo:** `support/templates/seller_console.html`

**Disposición de Botones Reorganizada:**

| Columna Izquierda | Columna Central | Columna Derecha |
| ----------------- | ----------------- | ----------------- |
| Rojo — Rechazados/Sin Contacto | Amarillo — Pendientes | Verde — Ventas y Agenda |
| No interesado | Llamar más tarde | Enviar promo / Vender |
| No llamar | **No encontrado** (nuevo) | Editar suscripción |
| Logística | Mover a la mañana | Agregar producto |
| Ya suscrito | Mover a la tarde | Cambiar producto |
| Error en promoción | | Agendar |
| No contactable | | |
| Cerrar sin contacto | | |

**Código de Colores en Lista de Contactos (tarjeta colapsable):**

| Color | Significado | Clase Bootstrap |
| ------- | ------------- | ----------------- |
| Naranja/Warning | Contacto marcado como "No encontrado" | `btn-warning text-dark` + ícono question-circle |
| Azul/Info | Contacto marcado como "Llamar más tarde" | `btn-info` |
| Gris | Contacto sin tocar | `btn-secondary` |
| Azul/Primary | Contacto actualmente activo | `btn-primary` |

**Badge en Encabezado de Tarjeta de Contacto:**

Al ver un contacto previamente marcado como "No encontrado" o "Llamar más tarde", aparece un badge junto al nombre del contacto mostrando la acción y la fecha/hora:

- 🟠 `ⓘ No encontrado — 27/02/2026 14:35`
- 🔵 `🕐 Llamar más tarde — 27/02/2026 10:20`

## Cambios en Base de Datos

### Migración: `core/migrations/0117_add_not_found_campaign_resolution.py`

- Se alteró el campo `campaign_resolution` en `ContactCampaignStatus` para incluir la nueva opción `NF`

### Migración: `support/migrations/0035_add_not_found_action_type.py`

- Se alteró el campo `action_type` en `SellerConsoleAction` para incluir la nueva opción `F` (No encontrado)
- Se alteró el campo `campaign_resolution` en `SellerConsoleAction` para incluir la nueva opción `NF`

## Flujo de Datos

Cuando un vendedor hace clic en "No encontrado":

1. **Formulario se envía** con `result = "not-found"`
2. **`handle_post_request`** busca `SellerConsoleAction` con slug `not-found`
3. **`process_activity_result`** actualiza `ContactCampaignStatus`:
   - `ccs.status = 3` (CALLED_COULD_NOT_CONTACT) — mantiene contacto en cola
   - `ccs.campaign_resolution = "NF"` — registra como "No encontrado"
   - `ccs.last_console_action = acción not-found` — para diferenciación de color
4. **Se crea Actividad** con referencia a `seller_console_action`
5. **Offset incrementado** en 1 — vendedor avanza al siguiente contacto
6. **En la próxima visita**, el contacto aparece en color naranja en la lista de contactos y un badge con fecha/hora en el encabezado de la tarjeta

## Beneficios

### Para Vendedores

- **Retroalimentación visual clara**: Ver instantáneamente qué contactos fueron previamente marcados como "no encontrado" o "llamar más tarde"
- **No destructivo**: Los contactos permanecen en la campaña para reintento
- **Visibilidad de fecha/hora**: Saber exactamente cuándo ocurrió la última acción sin buscar en actividades
- **Mejor disposición**: Acciones rojas (negativas) a la izquierda, amarillas (pendientes) en el medio, verdes (positivas) a la derecha — flujo más intuitivo

### Para Gerentes

- **Mejor seguimiento**: El código de resolución `NF` distingue "no encontrado" de "llamar más tarde" (`CL`) en reportes
- **Analíticas de campaña**: Pueden analizar cuántos contactos son inalcanzables vs. pendientes de llamada

## Uso

### Pasos de Despliegue

```bash
python manage.py migrate
python manage.py populate_seller_console_actions
```

### Uso para Vendedores

Un nuevo botón amarillo "No encontrado" aparece en la columna central. Haga clic cuando llame a un contacto pero no pueda localizarlo. El contacto:

- Le moverá al siguiente contacto en la lista
- Permanecerá en la campaña (se muestra en naranja al expandir la tarjeta de contactos)
- Mostrará un badge naranja con fecha/hora junto a su nombre cuando lo visite nuevamente

## Archivos Modificados

- `support/models.py` — Se agregó `NOT_FOUND = "F"` a `SellerConsoleAction.ACTION_TYPES`
- `core/choices.py` — Se agregó `("NF", _("Not found"))` a `CAMPAIGN_RESOLUTION_CHOICES`
- `core/management/commands/populate_seller_console_actions.py` — Se agregó entrada de acción `not-found`
- `support/views/seller_console.py` — Incremento de offset para NOT_FOUND, `select_related`, contexto `last_action_datetime`
- `support/templates/seller_console.html` — Reorganización de botones, nuevo botón, código de colores, badge en encabezado
- `core/migrations/0117_add_not_found_campaign_resolution.py` — Migración de resolución de campaña
- `support/migrations/0035_add_not_found_action_type.py` — Migración de tipo de acción

## Compatibilidad Hacia Atrás

- Los registros existentes de `SellerConsoleAction` no se ven afectados
- La nueva acción se crea mediante el comando de gestión
- Los campos nullable aseguran que no haya problemas con datos existentes
- Los contactos sin `last_console_action` se muestran normalmente (gris/secondary)
- Las plantillas de Django manejan silenciosamente atributos faltantes para instancias de categoría "act"

## Notas

- El tipo de acción `NOT_FOUND` es intencionalmente separado de `CALL_LATER` a pesar de compartir el mismo `campaign_status` (3). Esto permite tratamiento visual distinto y seguimiento analítico.
- El código de resolución `NF` es distinto de `UN` (No se puede encontrar contacto): `UN` termina la campaña, `NF` mantiene al contacto para reintento.
- El comando de gestión es idempotente — seguro de ejecutar múltiples veces.
