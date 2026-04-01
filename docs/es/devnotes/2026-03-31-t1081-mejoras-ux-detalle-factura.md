# Mejoras de UX en la Vista de Detalle de Factura

- **Fecha:** 2026-03-31
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1081
- **Tipo:** Mejora de UX
- **Componente:** Facturación
- **Impacto:** Experiencia de Usuario, Flujo de Trabajo del Operador

## 🎯 Resumen

Se realizaron varias mejoras pequeñas pero significativas en la vista de detalle de factura (`invoice_detail.html`). El botón "Editar" ahora abre el administrador de Django en una nueva pestaña del navegador para que los operadores no pierdan el contexto en el CRM mientras realizan ediciones en el admin. El botón "Anular factura" ahora se oculta cuando la factura ya está anulada, evitando una acción confusa y redundante. Cuando una factura anulada tiene una nota de crédito asociada, la vista de detalle ahora muestra la serie y el número de la nota de crédito junto con un enlace a su registro en el admin. Por último, se agregó una tarjeta de Notas para mostrar el campo `notes` de la factura, que existía en la base de datos pero nunca se mostraba en esta vista.

## ✨ Cambios

### 1. El botón Editar abre en una nueva pestaña

**Archivo:** `invoicing/templates/invoice/invoice_detail.html`

Se agregó `target="_blank"` al enlace de edición del admin para que al hacer clic en "Editar" se abra el formulario de cambio del administrador de Django en una nueva pestaña del navegador. Esto permite a los operadores revisar y modificar la factura en el admin sin salir de la vista de detalle del CRM.

### 2. Botón de anulación oculto para facturas ya anuladas

**Archivo:** `invoicing/templates/invoice/invoice_detail.html`

La condición de visibilidad del botón "Anular factura" se ajustó de `{% if perms.invoicing.can_cancel_invoice %}` a `{% if perms.invoicing.can_cancel_invoice and not object.canceled %}`. El botón ahora solo aparece cuando la factura sigue activa, eliminando una opción confusa en facturas que ya han sido anuladas.

### 3. Información de la nota de crédito mostrada cuando la factura está anulada

**Archivo:** `invoicing/templates/invoice/invoice_detail.html`

Cuando una factura está anulada y tiene una `CreditNote` asociada (accedida mediante `object.get_creditnote`), la sección de estado ahora muestra:

- La **serie y el número** de la nota de crédito (ej. `A-1042`) cuando esos campos están poblados — es decir, luego de que la nota de crédito fue enviada al proveedor de facturación electrónica.
- Un **enlace al formulario de cambio de la nota de crédito en el admin** (abre en nueva pestaña), visible solo para usuarios con el permiso `invoicing.change_creditnote`.

```html
{% with cnote=object.get_creditnote %}
  {% if cnote %}
    {% if cnote.serie and cnote.numero %}
      <strong>{{ cnote.serie }}-{{ cnote.numero }}</strong>
    {% endif %}
    {% if perms.invoicing.change_creditnote %}
      <a href="{% url "admin:invoicing_creditnote_change" cnote.id %}" target="_blank" ...>
        Ir a la nota de crédito en el admin
      </a>
    {% endif %}
  {% endif %}
{% endwith %}
```

Si la nota de crédito existe pero aún no fue enviada al proveedor (sin `serie`/`numero`), solo se muestra el enlace al admin sin el identificador.

### 4. Tarjeta de Notas

**Archivo:** `invoicing/templates/invoice/invoice_detail.html`

Se insertó una nueva tarjeta entre la tarjeta de Estado y la tarjeta de Datos de Facturación. Renderiza el contenido de `Invoice.notes` (un `TextField`) usando el filtro `|linebreaksbr`, y solo se muestra cuando el campo tiene contenido. El campo `notes` existe en el modelo desde hace tiempo pero no se mostraba en esta vista.

## 📁 Archivos Modificados

- **`invoicing/templates/invoice/invoice_detail.html`** — Botón Editar abre en nueva pestaña; botón de anulación oculto cuando ya está anulada; información y enlace a la nota de crédito mostrados al estar anulada; tarjeta de notas agregada

## 🧪 Pruebas Manuales

1. **Caso exitoso — botón Editar abre nueva pestaña:**
   - Abrir cualquier vista de detalle de factura como un usuario con `invoicing.change_invoice`.
   - Hacer clic en "Editar".
   - **Verificar:** El formulario de cambio del administrador de Django se abre en una nueva pestaña del navegador; la vista de detalle del CRM permanece abierta en la pestaña original.

2. **Caso exitoso — nota de crédito mostrada luego de la anulación:**
   - Abrir una factura anulada que tenga una nota de crédito con `serie` y `numero` poblados.
   - **Verificar:** La sección de Estado muestra el identificador de la nota de crédito (ej. `A-1042`) y un botón con enlace a la nota de crédito en el admin.

3. **Caso exitoso — tarjeta de notas visible:**
   - Abrir una factura cuyo campo `notes` tenga contenido (configurarlo desde el admin si es necesario).
   - **Verificar:** Aparece una tarjeta "Notes" entre las secciones de Estado y Datos de Facturación, con el texto renderizado respetando los saltos de línea.

4. **Caso borde — botón de anulación ausente en factura ya anulada:**
   - Abrir una factura anulada como usuario con `invoicing.can_cancel_invoice`.
   - **Verificar:** El botón "Anular factura" no se renderiza. En su lugar se muestran el badge "Cancelada" y la fecha de anulación.

5. **Caso borde — nota de crédito sin serie ni número:**
   - Abrir una factura anulada cuyo registro `CreditNote` exista pero tenga `serie` y `numero` nulos (nota de crédito aún no enviada al proveedor).
   - **Verificar:** El identificador de la nota de crédito no se muestra, pero el enlace "Ir a la nota de crédito en el admin" sigue apareciendo (para usuarios con el permiso correspondiente).

6. **Caso borde — tarjeta de notas ausente cuando notas está vacío:**
   - Abrir una factura cuyo campo `notes` sea nulo o esté en blanco.
   - **Verificar:** No aparece la tarjeta de Notas; el diseño pasa directamente de la tarjeta de Estado a la tarjeta de Datos de Facturación.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se necesitan cambios de configuración.
- No se introdujeron nuevos permisos; el enlace al admin de la nota de crédito respeta el permiso existente `invoicing.change_creditnote`.

---

- **Fecha:** 2026-03-31
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1081
- **Tipo de cambio:** Mejora de UX
- **Módulos afectados:** Facturación
