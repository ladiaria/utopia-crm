# Editar contacto: la consulta del email al CMS corre una sola vez por guardado

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#177
- **Tipo:** Rendimiento / Corrección de errores
- **Componente:** support (vista de edición de contacto)
- **Impacto:** Quien guarde un contacto desde «Editar contacto»

## 🎯 Resumen

Guardar un contacto desde «Editar contacto» tardaba unos 6 segundos en producción: en los logs de uWSGI, los 98 `POST /support/contacts/<id>/edit/` de los días anteriores tenían una mediana de 5,6 s y un p90 de 6,7 s. Unos 5 s de eso eran dos consultas iguales a la API `email_check` del CMS, de unos 2,5 s cada una (medido en producción el 2026-11-24).

`Contact.clean()` llama a `custom_clean()`, que le pregunta al CMS si el email está libre. Corría dos veces:

1. Cuando valida el `ModelForm`, dentro de su `_post_clean()`.
2. Cuando corre `Contact.save()`, porque `save()` llama a `clean()` salvo que esté `_skip_clean`.

`ContactUpdateView.form_valid` sí ponía `_skip_clean`, pero sólo alrededor de `form.save(False)`, que no guarda nada. Lo sacaba antes de `super().form_valid()`, que es donde se guarda de verdad, así que `save()` volvía a consultar con los mismos datos.

## ✨ Cambios

### 1. El flag sigue puesto durante el guardado de verdad

**Archivo:** `support/views/contacts.py`

`form_valid` pone `_skip_clean`, llama a `super().form_valid()` y saca el flag en un `finally`. Es el mismo patrón que ya usaba `ContactAdmin.save_model`. Se va la llamada a `form.save(False)`: no guardaba nada, y su `except` no podía atrapar una falla del guardado real.

### 2. El aviso de éxito sólo si se guardó

**Archivo:** `support/views/contacts.py`

«Contacto guardado» se agregaba antes del guardado real, así que salía aunque el guardado fallara y el formulario volviera con un error. Ahora se agrega después de que `super().form_valid()` vuelve.

## 📁 Archivos modificados

- **`support/views/contacts.py`** — `ContactUpdateView.form_valid`
- **`tests/test_edit_contact_view.py`** — Nuevo: una sola consulta del email por guardado, las etiquetas se guardan, un email rechazado no se guarda
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas manuales

1. **Caso normal:** cambiar el nombre de un contacto y guardar. **Verificar:** abre la ficha con «Contacto guardado» y el nombre nuevo.
2. **Caso borde, email ocupado en la web:** cambiar el email por uno que tiene otra cuenta web. **Verificar:** el formulario vuelve con el motivo del CMS, no se guarda nada y no sale «Contacto guardado».
3. **Producción:** después del deploy, la mediana de `POST /support/contacts/<id>/edit/` en `/var/log/uwsgi/utopia-crm.log` baja unos 2,5 s.

## 📝 Notas de despliegue

- Sin migraciones ni settings.

## 🎓 Decisiones de diseño

- **Por qué saltear la segunda consulta no pierde nada:** las dos corren sobre la misma instancia con los mismos datos. Lo que haga la primera (archivar un takeover, correr el dedupe, rechazar el email) ya está hecho cuando corre `save()`. Cuando archiva el takeover, la primera hasta vuelve a poner el email viejo, así que la segunda sólo confirmaba el email que el contacto ya tenía.
- **`email_check` tarda 2,5 s del lado del CMS.** Es lento para una búsqueda por email, pero vive en el CMS y queda fuera de este cambio.

---

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl177-email-check-una-vez
- **Tipo:** Rendimiento / Corrección de errores
- **Módulos afectados:** support
