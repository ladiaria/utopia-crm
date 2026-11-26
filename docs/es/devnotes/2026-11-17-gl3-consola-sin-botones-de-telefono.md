# La consola de ventas ya no borra ni valida teléfonos a mano

- **Fecha:** 2026-11-17
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#3
- **Tipo:** Cambio
- **Componente:** Support (consola de ventas, formulario de suscripción), Core (Contact)
- **Impacto:** Experiencia de Usuario, Datos

## 🎯 Resumen

Supervisión no quiere que los vendedores borren números desde la consola: borrar un número equivocado tiene que pasar por una regla acordada con ellos. Por eso se sacan los botones ✓ y ✗ que ladiaria/utopia-crm#457 puso en cada fila de Teléfono y Celular, y su endpoint. Validar un número pasa a ser sólo automático, cuando el contacto tiene un solo número y el vendedor habló con la persona: una llamada agendada, una rechazada o cerrada con contacto (salvo que el motivo diga que quien atendió no era la persona) y, como novedad, una venta desde la consola.

## ✨ Cambios

### 1. `Contact.validate_the_only_phone()`

**Archivo:** `core/models.py`

```python
contact.validate_the_only_phone(PhoneValidationSource.CALL_CENTER, user=request.user)
```

La regla que vivía en la vista de la consola pasa al modelo, para que la compartan el resultado de la llamada y la venta: si Teléfono o Celular es el único número del contacto (el Teléfono institucional cuenta como otro número), se valida con `mark_phone_validated()`. Devuelve el campo que validó, o `None`.

### 2. Una venta desde la consola valida el número

**Archivo:** `support/views/subscriptions.py`

`SubscriptionMixin.get_redirect_url_and_sales_record()` llama a `validate_the_only_phone()` cuando la venta viene de la consola: venta directa (`?new=`) o venta desde una actividad agendada (`?act=`). Lee el contacto de la base, porque un número escrito en el formulario puede no haberse guardado (por ejemplo, si el guardado falló contra la web). Una suscripción hecha desde la ficha del contacto no valida nada.

### 3. Se sacan los botones

**Archivos:** `support/templates/seller_console.html`, `support/views/seller_console.py`, `support/urls.py`, `support/views/__init__.py`

Las filas de Teléfono y Celular vuelven a ser como antes del #457, con la etiqueta «Validado» y sin botones. Se borran `seller_console_phone_row.html`, `phone_row()`, la vista `seller_console_phone` y su URL, y sus traducciones. `SellerConsoleView.validate_the_only_phone()` mantiene las condiciones del resultado de la llamada (Contactado o Finalizado con contacto, sin cambio de turno, motivo fuera de `SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS`) y le delega el resto al modelo.

`Contact.remove_phone()` se queda: ahora no lo llama nadie, pero es lo que va a usar la regla de borrado que se acuerde.

## 📁 Archivos Modificados

- **`core/models.py`** — `validate_the_only_phone()`
- **`support/views/seller_console.py`** — Sin `phone_row()` ni `seller_console_phone()`; `validate_the_only_phone()` usa el modelo
- **`support/views/subscriptions.py`** — La venta desde la consola valida el número
- **`support/templates/seller_console.html`** — Las filas de Teléfono y Celular sin botones
- **`support/urls.py`**, **`support/views/__init__.py`** — Sin la URL de los botones
- **`locale/es/LC_MESSAGES/django.po`** — Se sacan las traducciones de los botones
- **`tests/test_seller_console_phones.py`** — Sin los tests de los botones; tests del método del modelo, del agendado, de los dos motivos, de la venta y de la consola sin botones
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Borrados

- **`support/templates/seller_console_phone_row.html`** — La fila con los botones

## 🧪 Pruebas Manuales

1. **Caso normal, venta:**
   - En la consola, con un contacto de prueba que sólo tiene Celular, hacer una venta desde el botón «Vender».
   - **Verificar:** El Celular muestra «Validado», con origen Call center, y el historial del contacto (admin) tiene al vendedor como autor.

2. **Caso normal, agenda:**
   - Con otro contacto con un solo número, agendar una llamada.
   - **Verificar:** El número queda validado.

3. **Caso borde, motivo equivocado:**
   - Cerrar la llamada de un contacto con un solo número con «No interesado» y el motivo «Número y email incorrectos».
   - **Verificar:** El número no se valida ni se borra.

4. **Caso borde, dos números:**
   - Hacerle una venta a un contacto con Teléfono y Celular.
   - **Verificar:** No se valida ninguno.

5. **Sin botones:**
   - **Verificar:** Las filas de Teléfono y Celular de la consola no tienen ✓ ni ✗.

## 📝 Notas de Despliegue

- Sin migraciones.
- Sin settings nuevos. `SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS` sigue funcionando como antes.

## 🎓 Decisiones de Diseño

- **Sin un permiso para dejarle la ✗ a algunos:** se pensó en una ✗ con permiso, pero supervisión quiere una regla, no una persona decidiendo en la consola. Cuando se acuerde la regla, el borrado va a ser un script o un proceso, no un botón.
- **Tampoco el ✓:** sin la ✗, un ✓ solo invita a validar a ojo. Validar queda atado a lo que el vendedor ya registra: el resultado de la llamada o la venta.
- **Con dos números no se valida ninguno:** ni el CCS ni la actividad guardan a qué número se llamó, y validar los dos daría por bueno un número que puede estar mal.
- **La venta lee el contacto de la base:** el formulario puede cambiar los números, y si falló el guardado del contacto, el objeto en memoria tiene números que no están guardados.

---

- **Fecha:** 2026-11-17
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl3-consola-sin-botones
- **Tipo:** Cambio
- **Módulos afectados:** core, support
