# Un teléfono también se puede validar por WhatsApp

- **Fecha:** 2026-11-17
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#3
- **Tipo:** Funcionalidad
- **Componente:** Core (Contact)
- **Impacto:** Datos

## 🎯 Resumen

Si alguien nos escribe por WhatsApp, el número desde el que escribe es suyo. Este cambio agrega «WhatsApp» como origen de la validación de Teléfono y Celular, y un método para validar el campo que tiene exactamente el número del que vino un mensaje. Quien recibe los mensajes (en la diaria, el paquete de customización) lo llama.

## ✨ Cambios

### 1. `PhoneValidationSource.WHATSAPP`

**Archivos:** `core/choices.py`, `core/migrations/0127_phone_validation_source_whatsapp.py`

### 2. `Contact.validate_phone_number(number, source, when=None, user=None)`

**Archivo:** `core/models.py`

Normaliza el número (cualquier formato que acepten los campos de teléfono) y lo compara en E.164 con Teléfono y Celular. Valida el que coincide, con `mark_phone_validated()`. Devuelve el campo, o `None` si ninguno coincide o si el número ya estaba validado con una fecha igual o más nueva (no la retrocede).

La comparación es exacta a propósito: la búsqueda de quién llama por teléfono acepta coincidencias parciales, y una coincidencia parcial no prueba que el número sea el de la persona.

## 📁 Archivos Modificados

- **`core/choices.py`** — `PhoneValidationSource.WHATSAPP`
- **`core/models.py`** — `validate_phone_number()`
- **`tests/test_phone_validation.py`** — Tests del método
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`core/migrations/0127_phone_validation_source_whatsapp.py`** — Las opciones nuevas del origen

## 🧪 Pruebas Manuales

1. **Caso normal:** en un shell, `contact.validate_phone_number("099 123 456", PhoneValidationSource.WHATSAPP)` sobre un contacto con ese celular. **Verificar:** devuelve `"mobile"` y la ficha muestra «Validado» con origen WhatsApp.
2. **Caso borde:** con un número que el contacto no tiene, o una parte de él. **Verificar:** devuelve `None` y no cambia nada.

## 📝 Notas de Despliegue

- **Migración:** `core.0127_phone_validation_source_whatsapp`. Sólo cambia las opciones del campo: no toca datos.

---

- **Fecha:** 2026-11-17
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl3-validar-whatsapp
- **Tipo:** Funcionalidad
- **Módulos afectados:** core
