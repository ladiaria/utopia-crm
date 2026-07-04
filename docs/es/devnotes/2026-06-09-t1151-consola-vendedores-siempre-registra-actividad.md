# Corrección: La consola de vendedores omite el registro de actividad en acciones terminales y pierde la acción de consola al agendar

- **Fecha:** 2026-06-09
- **Autor:** Tanya Tree + Claude Opus 4.8
- **Ticket:** t1151
- **Tipo:** Corrección
- **Componente:** Support — Consola de Vendedores, Modelos Core (Activity, ContactCampaignStatus)
- **Impacto:** Integridad de Datos, Registro de Actividades, Reportes de Campaña

## 🎯 Resumen

Cuando un vendedor resolvía desde la consola un contacto aún no contactado con una acción terminal como "No interesado", el estado de campaña del contacto se actualizaba (por ejemplo a "Finalizado con contacto" con resolución "No interesado") pero **no se creaba ningún registro de `Activity`**. El contacto quedaba con el estado de campaña cerrado y la pestaña de Actividades vacía, lo que hacía imposible auditar qué había hecho realmente el vendedor. La causa era un `return` temprano en `register_new_activity` para cualquier acción cuyo `action_type` fuera `DECLINED`. Por separado, cuando un vendedor usaba la acción "Agendar", la actividad pendiente futura resultante (la llamada agendada) se creaba **sin** `seller_console_action`, por lo que esa llamada agendada no mostraba la acción "Agendar" en la lista de actividades. Este cambio hace que la consola siempre registre una actividad completada para cualquier resolución enviada por POST en la categoría `new` (incluso con notas vacías), y que la actividad pendiente agendada quede marcada con la acción de consola `schedule`.

## ✨ Cambios

### 1. Siempre registrar una actividad completada para acciones terminales en la categoría `new`

**Archivo:** `support/views/seller_console.py`

`register_new_activity` cortocircuitaba para acciones `DECLINED`, así que los contactos resueltos como "No interesado", "No llamar", "Logística", etc. desde la cola de no contactados nunca obtenían una actividad:

```python
# Antes — las acciones terminales dejaban al contacto sin actividad
seller_console_action = self.get_seller_console_action(result, required=False)
# If the ACTION_TYPE was DECLINED, we won't create a new activity
if seller_console_action.action_type == SellerConsoleAction.ACTION_TYPES.DECLINED:
    return
```

Se eliminó el `return` temprano y se reemplazó por una guarda defensiva para una acción ausente. El bloque final `category == "new"` ahora siempre crea una actividad completada, con las notas vacías convertidas a cadena vacía:

```python
# Después — cualquier resolución enviada por POST en "new" registra una actividad completada
seller_console_action = self.get_seller_console_action(result, required=False)
if not seller_console_action:
    return

# ... (ramas CALL_LATER / NOT_FOUND / KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY sin cambios) ...

if category == "new":
    Activity.objects.create(
        contact=contact,
        activity_type="C",
        datetime=datetime.now(),
        campaign=campaign,
        seller=seller,
        status="C",  # Completed
        notes=notes or "",
        seller_console_action=seller_console_action,
    )
```

El único camino que deja intencionalmente a un contacto sin actividad es el enlace "Omitir y pasar al siguiente contacto", que es un `<a href>` simple que solo cambia el `offset` y no envía un `result` por POST — por lo que nunca llega a este código.

### 2. Marcar la actividad pendiente agendada con la acción de consola

**Archivo:** `support/views/seller_console.py`

`create_scheduled_activity` no asignaba `seller_console_action`, así que la llamada futura agendada no tenía ninguna acción de consola asociada:

```python
# Antes
def create_scheduled_activity(self, contact, campaign, seller, call_datetime):
    return Activity.objects.create(
        contact=contact,
        activity_type="C",
        datetime=call_datetime,
        campaign=campaign,
        seller=seller,
        notes="{} {}".format(_("Scheduled for"), call_datetime),
    )
```

El método ahora recibe y asigna `seller_console_action`, y `handle_post_request` le pasa la acción `schedule`:

```python
# Después
def create_scheduled_activity(self, contact, campaign, seller, call_datetime, seller_console_action=None):
    return Activity.objects.create(
        contact=contact,
        activity_type="C",
        datetime=call_datetime,
        campaign=campaign,
        seller=seller,
        seller_console_action=seller_console_action,
        notes="{} {}".format(_("Scheduled for"), call_datetime),
    )

# en handle_post_request:
if seller_console_action.action_type == SellerConsoleAction.ACTION_TYPES.SCHEDULED:
    call_datetime = self.get_call_datetime(data)
    self.create_scheduled_activity(contact, campaign, seller, call_datetime, seller_console_action)
```

### 3. Tests de regresión

**Archivo:** `tests/test_seller_console.py` (nuevo)

Se agregaron dos clases de test:

- **`TestSellerConsoleRegistersActivity`** — verifica que una acción `DECLINED` ("not-interested") en la categoría `new` cree exactamente una actividad completada (con y sin notas), y que el `ContactCampaignStatus` se actualice con el estado, la resolución y el `last_console_action` de la acción.
- **`TestSellerConsoleScheduledActivity`** — verifica que agendar un contacto cree una actividad pendiente futura marcada con la acción de consola `schedule`.

## 📁 Archivos Modificados

- **`support/views/seller_console.py`** — Se eliminó el `return` temprano de `DECLINED` en `register_new_activity`; se convirtieron las notas vacías a `""`; se propagó `seller_console_action` a través de `create_scheduled_activity` y su llamador

## 📁 Archivos Creados

- **`tests/test_seller_console.py`** — Tests de regresión para el registro de actividad en acciones terminales y para la acción de consola de la actividad agendada

## 📚 Detalles Técnicos

**Por qué el bug solo aparecía en la cola `new`:**

La categoría `act` (contactos que ya tenían una actividad pendiente) actualiza la `Activity` existente en `handle_post_request` (asigna notas, estado a completado, datetime a ahora y la acción de consola), por lo que esos contactos siempre conservaban un registro. El bug de la actividad faltante solo afectaba a la cola `new` (no contactados aún), que dependía enteramente de `register_new_activity` — justamente el camino que retornaba temprano para `DECLINED`.

**Por qué es seguro marcar la actividad pendiente:**

Agendar crea dos actividades: una completada (el registro de que el vendedor agendó hoy, que ya llevaba la acción `schedule`) y una pendiente futura (la llamada por hacer). Cuando el vendedor atiende luego esa llamada pendiente desde la cola `act`, `handle_post_request` sobreescribe su `seller_console_action` con la resolución que el vendedor elija. Así, la actividad pendiente nace etiquetada como "Agendar" y se re-etiqueta con la resolución real al completarse.

## 🧪 Pruebas Manuales

1. **Caso exitoso — "No interesado" en un contacto nuevo crea una actividad:**
   - Abrir la consola de vendedores para una campaña en la categoría `new` con un contacto no contactado asignado al vendedor.
   - Hacer clic en "No interesado" y enviar (dejar las notas vacías).
   - **Verificar:** El estado de campaña del contacto pasa a "Finalizado con contacto" con resolución "No interesado", Y la pestaña de Actividades ahora muestra una actividad completada con la acción de consola "No interesado".

2. **Caso exitoso — agendar marca la llamada pendiente:**
   - En la categoría `new`, hacer clic en "Agendar", elegir una fecha/hora futura y enviar.
   - **Verificar:** Existe una actividad pendiente futura para la fecha elegida con la acción de consola "Agendar" asociada (visible/coloreada como tal en la cola de la consola).

3. **Caso borde — las notas vacías igual crean una actividad:**
   - Resolver un contacto nuevo con "No llamar" dejando el campo de notas vacío.
   - **Verificar:** Se crea una actividad completada con notas vacías y la acción de consola "No llamar".

4. **Caso borde — "Omitir y pasar al siguiente" NO crea una actividad:**
   - En un contacto nuevo, hacer clic en "Omitir y pasar al siguiente contacto".
   - **Verificar:** No se crea ninguna actividad y el estado de campaña no cambia; la consola simplemente avanza al siguiente contacto.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- El cambio es puramente a nivel de lógica dentro de la vista de la consola de vendedores. Los contactos históricos que se resolvieron sin actividad antes de esta corrección no se reprocesan.

## 🎓 Decisiones de Diseño

La corrección mantiene intencionalmente el enlace "Omitir y pasar al siguiente" como la única forma de dejar un contacto sin actividad, porque esa acción es una ayuda de navegación más que una resolución — no envía un `result` por POST. Toda acción que sí envía una resolución ahora produce una actividad, de modo que el registro de actividades se convierte en una traza de auditoría completa de las decisiones del vendedor. Las notas vacías se almacenan como cadena vacía en lugar de bloquear la acción, cumpliendo el requisito de que siempre debe crearse una actividad aun cuando el vendedor no escriba ningún comentario.

## 🚀 Mejoras Futuras

- Conservar la fecha originalmente agendada cuando se completa una actividad pendiente agendada (actualmente `datetime` se sobreescribe con `now()` al completarse, perdiendo la fecha para la que se había agendado la llamada). Registrado por separado, fuera de t1151.
- Exponer o cerrar automáticamente las actividades pendientes agendadas vencidas cuya fecha está muy atrás en el pasado y que nunca se atendieron.

---

**Fecha:** 2026-06-09
**Autor:** Tanya Tree + Claude Opus 4.8
**Branch:** t1151
**Tipo de cambio:** Corrección
**Módulos afectados:** Support, Core (Activity, ContactCampaignStatus)
