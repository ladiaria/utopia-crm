# Reactivación de Suscripciones: Edición de Método de Pago y Corrección de Fecha de Facturación

**Fecha:** 2026-03-23
**Autor:** Tanya Tree + programador AI en par
**Ticket:** t1062
**Tipo:** Mejora, Corrección
**Componente:** Support, Suscripciones
**Impacto:** Integridad de Datos, Experiencia de Usuario

## 🎯 Resumen

Se corrigieron dos problemas en el flujo de reactivación de suscripciones. Primero, la página de confirmación no permitía ver ni actualizar el método de pago de la suscripción, obligando al equipo a hacer una edición separada luego de reactivar. Segundo, la lógica de ajuste de la fecha de próxima facturación era incorrecta: en lugar de correr la fecha hacia adelante por todo el período de inactividad, la fijaba incondicionalmente en `hoy + 1 día`, lo que podía dejar al cliente siendo facturado demasiado pronto (o demasiado tarde). La página de reactivación ahora incluye un selector editable de método de pago y la fecha de facturación se corre correctamente la misma cantidad de días que la suscripción estuvo inactiva.

## ✨ Cambios

### 1. Corrección del Corrimiento de la Fecha de Próxima Facturación

**Archivo:** `support/views/subscriptions.py` — `reactivate_subscription()`

La lógica anterior reemplazaba `next_billing` por `hoy + 1` cada vez que estaba en el pasado. Esto ignoraba cuánto tiempo había estado inactiva la suscripción. La regla correcta es: correr `next_billing` hacia adelante `(hoy − end_date)` días, independientemente de si `next_billing` ya estaba en el pasado o todavía en el futuro — el cliente no debe ser cobrado por el período en que la suscripción estuvo pausada.

```python
# Capturar end_date antes de que sea limpiado
inactive_end_date = subscription.end_date
# ...limpiar campos de baja...
if subscription.next_billing and inactive_end_date and inactive_end_date < date.today():
    inactive_days = (date.today() - inactive_end_date).days
    subscription.next_billing += timedelta(days=inactive_days)
```

`inactive_end_date` se captura antes de limpiar los campos de baja, ya que `subscription.end_date` se establece en `None` como parte de la reactivación.

El handler GET también calcula un `new_next_billing` proyectado y lo pasa al template para que el equipo pueda previsualizar el ajuste antes de confirmar.

### 2. Método de Pago Editable en el Formulario de Reactivación

**Archivos:** `support/views/subscriptions.py`, `support/templates/reactivate_subscription.html`

El campo `payment_type` (un `CharField` con opciones de `settings.SUBSCRIPTION_PAYMENT_METHODS`) es el campo de método de pago en uso activo en `Subscription`. El template de reactivación ahora incluye un `<select>` para este campo con el valor actual de la suscripción preseleccionado. En el POST, el valor enviado se aplica a la suscripción antes del guardado:

```python
subscription.payment_type = request.POST.get("payment_type") or None
```

Una selección en blanco limpia el campo. Las opciones se pasan desde la vista mediante `payment_method_choices`:

```python
"payment_method_choices": settings.SUBSCRIPTION_PAYMENT_METHODS,
```

### 3. Filas Adicionales en la Tabla de Detalles

**Archivo:** `support/templates/reactivate_subscription.html`

La tabla de detalles de solo lectura ahora muestra tres filas adicionales:

- **Próxima facturación** — valor actual, con una flecha y el valor proyectado post-reactivación cuando se aplicará un ajuste (ej. `2026-03-10 → 2026-04-14 (adjusted for inactive period)`)
- **Método de pago** — valor de visualización actual del campo `payment_type`

## 📁 Archivos Modificados

- **`support/views/subscriptions.py`** — Corregida la lógica de corrimiento de `next_billing`; agregado manejo de `payment_type` en el POST; agregados `payment_method_choices` y `new_next_billing` al contexto del GET
- **`support/templates/reactivate_subscription.html`** — Agregadas filas de próxima facturación y método de pago en la tabla de detalles; agregado selector `payment_type` editable al formulario

## 🎓 Decisiones de Diseño

- **Solo `payment_type`, no `payment_method_fk`/`payment_type_fk`:** El modelo `Subscription` tiene campos FK más nuevos para el pago (`payment_method_fk`, `payment_type_fk`) pero no están conectados en ningún lugar de la aplicación. El campo legado `payment_type` de tipo char es el que usan la facturación, los filtros y los formularios existentes. Solo este campo se expone en el formulario de reactivación.
- **El corrimiento aplica incondicionalmente cuando `end_date` es pasado:** El corrimiento se aplica siempre que `end_date < hoy`, independientemente de si `next_billing` ya estaba en el pasado o en el futuro. Una suscripción facturada hasta el 1 de abril pero inactiva del 1 al 23 de marzo (22 días) debería tener su próxima facturación movida al 23 de abril — el cliente no recibió el servicio durante ese período.
- **El método de pago en blanco limpia el campo:** Un `<select>` HTML con primera opción en blanco y `or None` en Python significa que un envío en blanco limpia explícitamente el campo, consistente con el comportamiento habitual de Django admin para campos char nullables.

## 🧪 Pruebas Manuales

1. **Caso exitoso — corrimiento de fecha de facturación:**
   - Encontrar una suscripción con `end_date` en el pasado (ej. 1 de marzo) y una fecha `next_billing` que esté en el pasado o próximo futuro.
   - Navegar a su página de reactivación.
   - **Verificar:** La fila "Next billing" en la tabla de detalles muestra la fecha original, una flecha y la fecha proyectada con la nota "(adjusted for inactive period)".
   - Confirmar la reactivación.
   - Abrir la suscripción y verificar `next_billing`.
   - **Verificar:** `next_billing` es igual al valor original más la cantidad de días entre `end_date` y hoy.

2. **Caso exitoso — actualización de método de pago:**
   - Navegar a la página de reactivación de una suscripción.
   - Cambiar el selector de método de pago a un valor diferente.
   - Confirmar la reactivación.
   - Abrir el registro de la suscripción.
   - **Verificar:** `payment_type` refleja el valor seleccionado en el formulario de reactivación.

3. **Caso borde — limpiar el método de pago:**
   - Navegar a la página de reactivación de una suscripción que tiene `payment_type` asignado.
   - Cambiar el selector a la opción en blanco `"---------"`.
   - Confirmar la reactivación.
   - **Verificar:** `payment_type` queda nulo/vacío en la suscripción.

4. **Caso borde — sin ajuste de fecha cuando `end_date` es hoy o en el futuro:**
   - Encontrar (o crear) una suscripción cuyo `end_date` sea hoy o en el futuro.
   - Navegar a su página de reactivación.
   - **Verificar:** La fila "Next billing" muestra solo el valor actual — no aparece flecha ni nota de ajuste.
   - Confirmar la reactivación.
   - **Verificar:** `next_billing` queda sin cambios.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- No hay comandos a ejecutar post-despliegue.

---

**Fecha:** 2026-03-23
**Autor:** Tanya Tree + programador AI en par
**Branch:** t1062
**Tipo de cambio:** Mejora, Corrección
**Módulos afectados:** Support, Suscripciones
