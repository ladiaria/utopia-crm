# Se borra la vista de factura suelta que quedó sin terminar

- **Fecha:** 2026-11-20
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#18
- **Tipo de cambio:** Refactor
- **Componente:** Invoicing
- **Impacto:** Ninguno para los usuarios (código muerto)

## 🎯 Resumen

`InvoiceNonSubscriptionCreateView` era una pantalla para crear a mano una factura suelta, sin suscripción. Entró el 2024-08-14 con la API de facturas de única vez (`1d2e1b4d`), y dos días después se le comentó la URL con `WIP: UI for creating invoices, unfinished. Uncomment when ready.` (`59104e57`). Nunca se terminó. Sin URL nadie podía llegar a ella, y además estaba rota: llamaba a `Contact.add_single_invoice_with_products(products)` sin el `payment_type` obligatorio, así que habría tirado `TypeError` si alguien la hubiera enchufado. Este cambio la borra junto con su formulario y su template.

## ✨ Cambios

### 1. La vista y su URL comentada

**Archivos:** `invoicing/views.py`, `invoicing/urls.py`

- Se borra `InvoiceNonSubscriptionCreateView`, y también el bloque comentado de `new_non_subscription/<int:contact_id>/` (`create_non_subscription_invoice`).
- Ya no se importa `CreateView`: esta vista era la única que lo usaba. Los demás imports que usaba (`staff_member_required`, `method_decorator`, `get_object_or_404`, `Contact`, `settings`) los siguen usando otras vistas y se quedan.

### 2. El formulario y el template

**Archivos:** `invoicing/forms.py`, `invoicing/templates/invoice_non_subscription_form.html`

`invoicing/forms.py` sólo tenía `InvoiceForm` e `InvoiceItemFormSet`, que sólo usaba esta vista, así que se borra el módulo entero.

## 📁 Archivos Modificados

- **`invoicing/views.py`** — Se borra `InvoiceNonSubscriptionCreateView` y los imports que sólo usaba ella
- **`invoicing/urls.py`** — Se borra la URL comentada
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Borrados

- **`invoicing/forms.py`** — `InvoiceForm` e `InvoiceItemFormSet`
- **`invoicing/templates/invoice_non_subscription_form.html`** — El template de la vista

## 📚 Detalles Técnicos

Antes de borrar se buscó en todo `~/git` (el base, el paquete de la diaria, rponline, los repos del CMS y la documentación) `InvoiceNonSubscriptionCreateView`, `create_non_subscription_invoice`, `invoice_non_subscription_form`, `InvoiceForm`, `InvoiceItemFormSet` e `invoicing.forms`. Fuera de estos archivos sólo aparecieron en clones viejos de una instalación que ya no usa el CRM. `OneshotDirectInvoiceForm`, del paquete de la diaria, es otra clase y no se ve afectada.

Las cadenas del template quedan en `locale/es/LC_MESSAGES/django.po` con referencias `#:` viejas. No molestan, y el próximo `makemessages -l es` las marca como obsoletas.

## 🧪 Pruebas Manuales

1. **Las pantallas de facturación siguen andando:** abrir las facturas de un contacto, el detalle de una factura y el filtro de facturas. **Verificar:** cargan como antes.
2. **La URL vieja no existe:** abrir `/invoicing/new_non_subscription/1/`. **Verificar:** 404, como antes (la URL ya estaba comentada).

## 📝 Notas de Despliegue

- No se requieren migraciones. Sin settings.

---

- **Fecha:** 2026-11-20
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl18-gl91-codigo-muerto
- **Tipo de cambio:** Refactor
- **Módulos afectados:** Invoicing
