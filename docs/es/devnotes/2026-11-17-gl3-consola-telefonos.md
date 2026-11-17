# La consola de ventas valida o borra cada teléfono

- **Fecha:** 2026-11-17
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#3
- **Tipo:** Funcionalidad
- **Componente:** Support (consola de ventas), Core (Contact)
- **Impacto:** Experiencia de Usuario, Datos

## 🎯 Resumen

Los campos de validación de Teléfono y Celular (ladiaria/utopia-crm#456) no tenían cómo llenarse desde el trabajo de todos los días. Ahora la consola de ventas tiene, en cada número, un botón ✓ que lo valida y uno ✗ que lo borra por número equivocado. Además, cerrar una llamada en la que se habló con la persona valida el número sin tocar nada cuando el contacto tiene uno solo: con dos, la consola no sabe en cuál contestó, y lo marca el vendedor.

## ✨ Cambios

### 1. `Contact.mark_phone_validated()` y `Contact.remove_phone()`

**Archivo:** `core/models.py`

```python
contact.mark_phone_validated("mobile", PhoneValidationSource.CALL_CENTER, user=request.user)
contact.remove_phone("phone", user=request.user, reason="Número equivocado, ...")
```

Los dos guardan sólo los campos que cambian con `bulk_update_with_history`: queda un registro en el historial, con el usuario y el motivo, y no pasan por `save()`. Así no disparan la sincronización con la web por contacto, igual que los scripts que limpiaron los teléfonos. `remove_phone` vacía también la validación del número y, en el Teléfono, la extensión.

### 2. Los botones

**Archivos:** `support/templates/seller_console_phone_row.html`, `support/templates/seller_console.html`, `support/views/seller_console.py`, `support/urls.py`

Las filas de Teléfono y Celular de la consola pasan a un template propio, que arma `phone_row()`. Los botones hacen un POST con htmx a `seller_console_phone/<contact_id>/<campo>/<validate|remove>/`, que responde con la fila nueva. La ✗ pregunta antes (`hx-confirm`). El POST trae el número que vio el vendedor: si cambió mientras tanto, no se toca nada y la fila muestra el actual. La vista exige staff, CSRF, POST y htmx, y acepta sólo `phone` y `mobile`.

### 3. Validación al cerrar la llamada

**Archivo:** `support/views/seller_console.py`

`SellerConsoleView.validate_the_only_phone()` corre después de guardar el CCS. Valida el número cuando:

- la acción deja el CCS en Contactado o Finalizado con contacto (no un cambio de turno);
- el motivo no está en `SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS`;
- el contacto tiene un solo número entre Teléfono, Celular y Teléfono de trabajo, y es Teléfono o Celular.

## 📁 Archivos Modificados

- **`core/models.py`** — `mark_phone_validated()`, `remove_phone()` y `_save_phone_fields()`
- **`support/views/seller_console.py`** — `phone_row()`, `seller_console_phone()` y `validate_the_only_phone()`
- **`support/templates/seller_console.html`** — Las filas de Teléfono y Celular, con el template nuevo
- **`support/urls.py`**, **`support/views/__init__.py`** — La URL de los botones
- **`locale/es/LC_MESSAGES/django.po`** — Traducciones
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`support/templates/seller_console_phone_row.html`** — Una fila de Teléfono o Celular, con sus botones
- **`tests/test_seller_console_phones.py`** — Los métodos del modelo, los botones y la validación al cerrar la llamada

## 🧪 Pruebas Manuales

1. **Caso normal, validar:**
   - En la consola, con un contacto de prueba con dos números, tocar ✓ en uno.
   - **Verificar:** Aparece «Validado» al lado del número, queda sólo la ✗, y lo escrito en la actividad sigue ahí.

2. **Caso normal, borrar:**
   - Tocar ✗ en el otro número y aceptar la pregunta.
   - **Verificar:** El número queda tachado con «Borrado por número equivocado»; en el historial del contacto (admin) está el número, el usuario y el motivo.

3. **Caso borde, un solo número:**
   - Cerrar la llamada de un contacto con un solo número con «No interesado» y un motivo cualquiera, salvo los del setting.
   - **Verificar:** El número queda validado, con origen Call center.

## 📝 Notas de Despliegue

- Sin migraciones.
- **Setting nuevo, opcional:** `SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS`, los motivos (`resolution_reason`) con los que cerrar la llamada no valida el número. Sin el setting, cualquier motivo valida. En la diaria van «Número y email incorrectos» (12) y «Falleció» (14): `(12, 14)`.

## 🎓 Decisiones de Diseño

- **Un número equivocado se borra, no se marca:** ver las devnotes de #456.
- **Con dos números, valida el vendedor:** el CCS y la actividad no guardan qué número se marcó. Validar los dos a ciegas daría por bueno un número que puede estar mal.
- **El Teléfono de trabajo cuenta como otro número** para la validación al cerrar: si el contacto lo tiene, la llamada pudo ser a ése.
- **Sin botón para sacar una validación:** un ✓ por error es raro y se corrige desde supervisión. Un botón más en cada fila confundía más de lo que ayudaba.

---

- **Fecha:** 2026-11-17
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl3-consola-telefonos
- **Tipo:** Funcionalidad
- **Módulos afectados:** core, support
