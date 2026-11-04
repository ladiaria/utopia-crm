# Los ítems de factura ya no tienen una pantalla propia en el admin

- **Fecha:** 2026-11-04
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl96-sacar-admin-invoiceitem (it/utopia-crm-ladiaria#96)
- **Tipo:** Corrección
- **Componente:** Invoicing (admin)
- **Impacto:** Rendimiento, Disponibilidad

## 🎯 Resumen

Abrir la pantalla de edición de un ítem de factura en el admin podía tirar todo el CRM. `InvoiceItemAdmin` no tenía configuración, así que la pantalla armaba un desplegable con todas las facturas y otro con todas las suscripciones. En producción, con millones de facturas, el worker que la atendía siguió creciendo después de que el navegador se rindiera, llegó a 6,9 GB en un servidor de 8 GB y el sistema operativo lo mató, y otros usuarios recibieron errores 502 durante unos segundos. Nada usaba esa pantalla: los ítems se ven y se editan en el inline de su factura. Por eso se saca en lugar de repararla.

## ✨ Cambios

### 1. `InvoiceItem` ya no está registrado en el admin

**Archivo:** `invoicing/admin.py`

Se saca `InvoiceItemAdmin`. Quedan `InvoiceItemInline`, el admin de facturas y los paquetes de customización que reutilizan el inline.

### 2. Tests

**Archivo:** `tests/test_invoice_admin.py`

- `InvoiceItem` no tiene un admin propio, para que nadie vuelva a agregar la pantalla sin ver este test y su motivo.
- La pantalla de edición de la factura sigue mostrando sus ítems en el inline.

## 📁 Archivos Modificados

- **`invoicing/admin.py`** — Se saca `InvoiceItemAdmin`.
- **`tests/test_invoice_admin.py`** — Nueva clase `TestInvoiceItemOnlyThroughInvoice`.
- **`CHANGELOG.md`** — Entrada.

## 📁 Archivos Creados

- **`docs/en/devnotes/2026-11-04-gl96-remove-invoice-item-admin.md`** — Versión en inglés.
- **`docs/es/devnotes/2026-11-04-gl96-sacar-admin-de-items-de-factura.md`** — Esta nota.

## 📚 Detalles Técnicos

- **Por qué no ayudó que el navegador se rindiera:** el pedido sigue corriendo en el worker mientras Django arma la página, así que cerrar la pestaña no libera la memoria.
- **Permisos:** el modelo `InvoiceItem` y sus permisos quedan, porque el inline depende de ellos. Los grupos que los tienen los conservan.
- **Enlaces viejos:** `/admin/invoicing/invoiceitem/` ahora responde 404. Ningún template, vista o `reverse()` de los repositorios conocidos apunta ahí.

## 🧪 Pruebas Manuales

1. **Ítems en la factura (caso feliz):**
   - Abrir en el admin una factura que tenga ítems (`/admin/invoicing/invoice/<id>/change/`).
   - **Verificar:** la pantalla carga rápido, sus ítems aparecen en el inline y se pueden editar.

2. **La pantalla ya no está (caso borde):**
   - Ir a `/admin/invoicing/invoiceitem/` y a `/admin/invoicing/invoiceitem/1/change/`.
   - **Verificar:** las dos responden 404, y la sección de facturación del índice del admin ya no lista los ítems de factura.

## 📝 Notas de Despliegue

- No se requieren migraciones.
- No hay traducciones nuevas.
- Un paquete de customización que importe `InvoiceItemAdmin` desde `invoicing.admin` fallaría al importarlo. Ninguno de los conocidos lo hace: sólo importan `InvoiceItemInline`.

## 🎓 Decisiones de Diseño

- **Sacarla en vez de agregar `raw_id_fields`:** el arreglo sería igual de corto, pero dejaría una pantalla que nadie usa y que puede editar un importe sin pasar por su factura. El inline ya cubre eso.

## 🚀 Mejoras Futuras

- La pantalla de alta de suscripciones tiene un problema parecido y más chico: `SubscriptionAdminForm` sólo filtra `billing_address` por contacto al editar, así que al crear lista todas las direcciones.
- Un límite de memoria por worker en uWSGI (`evil-reload-on-rss`) protege a cada instalación de cualquier pantalla con este problema. Es parte de la configuración de cada servidor.

---

- **Fecha:** 2026-11-04
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl96-sacar-admin-invoiceitem
- **Tipo de cambio:** Corrección
- **Módulos afectados:** Invoicing
