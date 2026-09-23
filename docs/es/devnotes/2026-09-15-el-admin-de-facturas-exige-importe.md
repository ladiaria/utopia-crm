# El admin de facturas exige el importe

- **Fecha:** 2026-09-15
- **Autor:** Tanya Tree + Claude Opus 5
- **Ticket:** fix/invoice-admin-amount-required
- **Tipo:** Corrección de bug
- **Componente:** Facturación (admin)
- **Impacto:** Integridad de datos, Cobranza

## 🎯 Resumen

El admin de Django permitía guardar una factura con el importe vacío, porque `Invoice.amount` es
`null=True, blank=True` y el formulario del admin lo heredaba. En la diaria, una factura editada así entró al
archivo que se manda cada noche a una red de cobranza (SISTARBANC), que rechazó el **archivo entero** por ese único
importe vacío. Durante cinco días ninguna factura nueva se pudo pagar por esa red. Ahora el formulario del admin
exige el importe.

## ✨ Cambios

### 1. Formulario del admin con importe obligatorio

**Archivo:** `invoicing/admin.py`

Nuevo `InvoiceAdminForm`, asignado como `InvoiceAdmin.form`. Mantiene todos los campos del modelo y sólo marca
`amount` como obligatorio:

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if "amount" in self.fields:
        self.fields["amount"].required = True
```

El `if` cubre las subclases que saquen `amount` de los fieldsets o lo pongan como sólo lectura: en ese caso el
campo no está en el formulario y no hay nada que exigir.

Los paquetes de customización que extienden `InvoiceAdmin` (como `InvoiceAdminWithExtension` en
`utopia_crm_ladiaria`) heredan el formulario sin cambiar nada de su lado.

## 📁 Archivos modificados

- **`invoicing/admin.py`** — `InvoiceAdminForm` con `amount` obligatorio, usado por `InvoiceAdmin`.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 📁 Archivos creados

- **`tests/test_invoice_admin.py`** — Arma el formulario del admin que esté registrado para `Invoice` y verifica que
  rechace un importe vacío y acepte uno completo. El test del importe vacío falla sin el cambio.

## 📚 Detalles técnicos

- **El modelo no cambia.** Pasar la columna a `NOT NULL` exigiría una migración de datos para las facturas viejas
  sin importe y afectaría todos los caminos que crean facturas. El problema fue una persona guardando un campo vacío
  a mano, y eso sólo pasa en el admin.
- **El cero se sigue aceptando.** Hay facturas legítimas en cero. Los exports que no pueden mandar un importe cero
  tienen que filtrarlo ellos (en la diaria, el export a SISTARBANC saltea importes nulos, cero y negativos y manda
  un aviso).
- **Las facturas viejas sin importe** se siguen pudiendo ver en el admin, pero para guardarlas hay que completarlo.
- No hay textos nuevos para traducir: el error es el mensaje estándar de Django "Este campo es obligatorio.".

## 🧪 Pruebas manuales

1. **Editar con importe (caso exitoso):**
   - Abrir una factura en el admin, cambiar las notas y guardar.
   - **Verificar:** se guarda como antes.

2. **Borrar el importe (caso borde):**
   - Abrir una factura en el admin, vaciar el importe y guardar.
   - **Verificar:** vuelve el formulario con "Este campo es obligatorio." en el importe, y el historial de la
     factura no tiene una entrada nueva.

3. **Importe cero:**
   - Poner el importe en `0` y guardar.
   - **Verificar:** se guarda.

## 📝 Notas de despliegue

- No se requieren migraciones de base de datos.
- No hay traducciones para compilar.
- No hay cambios de configuración.

## 🚀 Mejoras futuras

- Evaluar validar el importe a nivel de modelo (`clean`) para que otros formularios e importaciones tengan la misma
  regla, después de revisar cuántas facturas existentes no tienen importe.

---

- **Fecha:** 2026-09-15
- **Autor:** Tanya Tree + Claude Opus 5
- **Branch:** fix/invoice-admin-amount-required
- **Tipo:** Corrección de bug
- **Módulos afectados:** Facturación
