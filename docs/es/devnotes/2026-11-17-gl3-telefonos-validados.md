# Cada teléfono del contacto guarda si está validado

- **Fecha:** 2026-11-17
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#3
- **Tipo:** Funcionalidad
- **Componente:** Core (Contact), Support (ficha del contacto, consola de ventas)
- **Impacto:** Datos, Experiencia de Usuario

## 🎯 Resumen

El call center no tenía cómo saber si un número ya se confirmó como de la persona o si nadie lo probó nunca. Ahora Teléfono y Celular (`phone`, `mobile`) guardan cuándo se validaron y por qué vía: call center, llamada entrante o web. La ficha del contacto y la consola de ventas muestran una etiqueta «Validado» al lado del número, con la fecha y el origen en el tooltip. Cambiar el número le saca la validación, salvo que el mismo cambio valide el número nuevo.

Este PR pone los campos y su regla. Quién valida (la carga inicial con la lista de Distribución, los botones de la consola) llega en otros cambios.

## ✨ Cambios

### 1. Campos nuevos en `Contact`

**Archivos:** `core/models.py`, `core/choices.py`, `core/migrations/0126_contact_phone_validation.py`

```python
phone_validated_at = models.DateTimeField(blank=True, null=True, ...)
phone_validation_source = models.CharField(blank=True, default="", max_length=16,
                                           choices=PhoneValidationSource.choices, ...)
mobile_validated_at = ...
mobile_validation_source = ...
```

`PhoneValidationSource`: `call_center`, `incoming_call`, `web`. Un número sin fecha está sin verificar. `work_phone` no lleva validación: ahí van números que la persona confirma que estén aunque no pasen `PhoneNumberField`.

### 2. Cambiar el número le saca la validación

**Archivo:** `core/models.py`

`Contact.from_db` guarda los números y sus fechas tal como se leyeron, y `save()` llama a `reset_changed_phone_validations()`. Si un número cambió y su fecha no, vacía la fecha y el origen. Si cambiaron los dos, quien cambió el número también validó el nuevo, y se respeta. Se comparan los números normalizados: `099 123 456` y `+59899123456` son el mismo y no pierden la validación. Con `update_fields` cuentan sólo los números que se guardan, y los campos que se vacían se suman a la lista.

`bulk_update()` y `update()` no pasan por `save()`: quien cambie números en masa vacía la validación a mano.

### 3. La etiqueta «Validado»

**Archivos:** `support/templates/includes/_phone_validation.html`, `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/_information.html`, `support/templates/seller_console.html`

Un include que recibe la fecha y el origen, y no muestra nada si el número está sin verificar.

### 4. Admin

**Archivo:** `core/admin.py`

Los cuatro campos se ven en la ficha del contacto del admin, sólo de lectura: la validación la ponen los procesos que confirman el número.

## 📁 Archivos Modificados

- **`core/models.py`** — Los campos, `from_db`, `reset_changed_phone_validations()` y el `save()`
- **`core/choices.py`** — `PhoneValidationSource`
- **`core/admin.py`** — Los campos, de sólo lectura
- **`support/templates/contact_detail/tabs/_overview.html`**, **`_information.html`**, **`support/templates/seller_console.html`** — La etiqueta al lado de cada número
- **`locale/es/LC_MESSAGES/django.po`** — Traducciones
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`core/migrations/0126_contact_phone_validation.py`** — Los campos en `Contact` y `HistoricalContact`
- **`support/templates/includes/_phone_validation.html`** — La etiqueta
- **`tests/test_phone_validation.py`** — La regla del `save()`, la etiqueta en la ficha y el admin

## 🧪 Pruebas Manuales

1. **Caso normal, un número validado:**
   - En un shell, ponerle a un contacto `phone_validated_at` y `phone_validation_source="call_center"` con `update()`.
   - **Verificar:** La ficha (vista general e Información) y la consola de ventas muestran «Validado» al lado del teléfono, y el tooltip dice la fecha y «Call center».

2. **Caso normal, cambiar el número:**
   - Editar el teléfono de ese contacto desde la ficha.
   - **Verificar:** La etiqueta desaparece y el admin muestra los dos campos vacíos.

3. **Caso borde, el mismo número escrito distinto:**
   - Editar el teléfono y guardarlo con espacios o sin el prefijo internacional.
   - **Verificar:** La etiqueta sigue.

## 📝 Notas de Despliegue

- **Migración:** `core.0126_contact_phone_validation`. Agrega cuatro columnas a `core_contact` y a `core_historicalcontact`. Desde PostgreSQL 11, una columna nueva con valor por defecto no reescribe la tabla, así que corre rápido aun con millones de filas.
- Sin settings nuevos.

## 🎓 Decisiones de Diseño

- **Un número inválido se borra, no se marca.** Un número guardado como inválido lo seguirían usando todos los que leen `phone` y `mobile` directo (avisos por SMS, WhatsApp, la búsqueda de quién llama, exports, el sync con la web), y cada uno tendría que aprender a saltearlo. El historial del contacto ya guarda el número borrado, con la fecha, el usuario y el motivo. Así lo que está en el campo está validado o sin verificar, nunca «sabemos que está mal».
- **Fecha y origen en lugar de un booleano:** la fecha permite reglas como «validado en los últimos 3 años», y el origen dice cuánto pesa la validación. La fecha vacía ya es el «no».
- **La regla en `save()` y no en los formularios:** el número cambia desde la ficha, el admin, la API de la web y los procesos de un paquete de customización. Ponerla en el modelo la cubre en todos.
- **Las etiquetas Teléfono 1 / Teléfono 2 quedan para otro cambio:** tocan textos de toda la interfaz.

---

- **Fecha:** 2026-11-17
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl3-telefonos-validados
- **Tipo:** Funcionalidad
- **Módulos afectados:** core, support
