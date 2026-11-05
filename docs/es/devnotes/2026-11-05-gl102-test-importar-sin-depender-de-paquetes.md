# El test de importar contactos no depende de un paquete de customización

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#102
- **Tipo:** Corrección de error
- **Componente:** Tests
- **Impacto:** Sólo la suite de tests

## 🎯 Resumen

`test_import_with_invalid_document_type` esperaba que el contacto importado quedara sin tipo de documento. Un paquete de customización puede tipificar los documentos que llegan sin tipo al guardar el contacto, así que el test fallaba con uno instalado. Ahora comprueba que el tipo inválido no se crea.

## ✨ Cambios

### 1. La aserción

**Archivo:** `tests/test_import_contacts.py`

`assertIsNone(contact.id_document_type)` pasa a comprobar que no existe un `IdDocumentType` llamado `INVALID_TYPE`. El test sigue comprobando que el contacto se crea, que conserva su número de documento y que se muestra el aviso.

## 📁 Archivos Modificados

- **`tests/test_import_contacts.py`** — La aserción

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - Correr `tests.test_import_contacts` con el paquete de customización instalado y sus tipos de documento cargados.
   - **Verificar:** Pasa.

2. **Caso borde, sin paquete:**
   - Correrlo sin un paquete de customización.
   - **Verificar:** También pasa. No se corrió para este cambio.

## 📝 Notas de Despliegue

No se requieren migraciones. Sólo cambia un test.

---

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl102-test-import-tipo-documento
- **Tipo:** Corrección de error
- **Módulos afectados:** tests
