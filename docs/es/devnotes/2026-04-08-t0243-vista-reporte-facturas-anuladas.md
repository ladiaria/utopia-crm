# Vista de Reporte de Facturas Anuladas

- **Fecha:** 2026-04-08
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t0243
- **Tipo:** Funcionalidad
- **Componente:** Facturación
- **Impacto:** Flujo de trabajo del operador, Control de acceso, Rendimiento

## 🎯 Resumen

Se agregó una nueva `CanceledInvoicesReportView` a la app `invoicing`, incorporando el reporte CSV de facturas anuladas al CRM base de código abierto. Este reporte existía anteriormente solo como una vista de función (`facturas_anuladas`) dentro del paquete de personalización privado `utopia-crm-ladiaria`. Moverlo a la app base lo hace disponible para todos los despliegues, aplica el control de acceso de forma consistente y corrige problemas potenciales de consultas N+1 que tenía la vista de función original.

## ✨ Cambios

### 1. Vista basada en clase con control de acceso

**Archivo:** `invoicing/views.py`

`CanceledInvoicesReportView` es una vista basada en clase que combina `BreadcrumbsMixin`, `UserPassesTestMixin` y `TemplateView`. El acceso es restringido por `test_func` a miembros del grupo `"Admins"`, el grupo `"Finances"` y superusuarios:

```python
def test_func(self):
    user = self.request.user
    return user.is_superuser or user.groups.filter(name__in=["Admins", "Finances"]).exists()
```

`GET` renderiza un formulario simple de rango de fechas usando pickers HTML5 `<input type="date">`. `POST` consulta las facturas anuladas dentro del rango de fechas enviado, transmite los resultados como descarga CSV y devuelve un `HttpResponse` con `Content-Type: text/csv`.

### 2. Prevención de N+1 con prefetch_related

**Archivo:** `invoicing/views.py`

El queryset usa `prefetch_related` para cargar los ítems de factura y las notas de crédito en dos consultas adicionales en lugar de una por factura:

```python
Invoice.objects.filter(
    canceled=True,
    cancelation_date__date__range=(date_from, date_to),
).prefetch_related("invoiceitem_set", "creditnote_set")
```

Esto mantiene la vista rápida en rangos de fechas que devuelven cientos de facturas.

### 3. Encabezados de columnas CSV con traducción

**Archivo:** `invoicing/views.py`

Todos los encabezados de columna pasados a `csv.writer` están envueltos en `_()` para que respeten el idioma activo de la instalación Django:

```python
writer.writerow([
    _("Invoice number"), _("Date"), _("Contact"), _("Amount"),
    _("Cancelation date"), _("Credit note"), ...
])
```

### 4. Registro de URL

**Archivo:** `invoicing/urls.py`

Una nueva URL con nombre `canceled_invoices_report` mapea la ruta `canceled_invoices_report/` a la nueva vista.

### 5. Template

**Archivo:** `invoicing/templates/canceled_invoices_report.html`

Una card de AdminLTE con un formulario mínimo: dos inputs de fecha HTML5 (Desde / Hasta) y un botón de envío. El formulario usa `method="post"` para que el rango de fechas se envíe en el cuerpo de la solicitud en lugar de la URL, de forma consistente con otras vistas de reporte en la app.

## 📁 Archivos Modificados

- **`invoicing/views.py`** — Se agregó `CanceledInvoicesReportView` y se actualizaron los imports
- **`invoicing/urls.py`** — Se agregó la URL `canceled_invoices_report/` y el import de la nueva vista

## 📁 Archivos Creados

- **`invoicing/templates/canceled_invoices_report.html`** — Formulario de rango de fechas para la descarga del reporte

## 📚 Detalles Técnicos

- `UserPassesTestMixin` redirige automáticamente a los usuarios no autenticados a la página de login; los usuarios autenticados que no pasan `test_func` reciben una respuesta 403.
- La vista responde a `GET` y `POST` dentro de la misma clase. `get()` renderiza el formulario; `post()` valida las fechas, construye el queryset y devuelve la respuesta CSV.
- `prefetch_related("invoiceitem_set", "creditnote_set")` se evalúa de forma diferida al iterar dentro de `post()`, por lo que no se ejecutan consultas adicionales en `GET`.
- La vista de función original `facturas_anuladas` en `utopia-crm-ladiaria` puede eliminarse o redirigirse a esta URL una vez que esta versión esté desplegada en todos los entornos que la utilizaban.

## 🧪 Pruebas Manuales

1. **Caso exitoso — usuario de Finances descarga el reporte:**
   - Iniciar sesión como usuario en el grupo `"Finances"`.
   - Navegar a `invoicing/canceled_invoices_report/`.
   - **Verificar:** La página carga con un formulario de rango de fechas (dos date pickers y un botón de envío).
   - Ingresar un rango de fechas que incluya facturas anuladas conocidas y enviar.
   - **Verificar:** Se descarga un archivo CSV. Abrirlo y confirmar que las columnas están presentes y los datos coinciden con las facturas anuladas esperadas dentro del rango.

2. **Caso exitoso — superusuario descarga el reporte:**
   - Iniciar sesión como superusuario.
   - Navegar a `invoicing/canceled_invoices_report/` y enviar un rango de fechas.
   - **Verificar:** El CSV se descarga correctamente, igual que en el caso anterior.

3. **Caso borde — usuario sin el grupo requerido es rechazado:**
   - Iniciar sesión como un usuario staff normal que no está en `"Admins"` ni `"Finances"` y no es superusuario.
   - Navegar a `invoicing/canceled_invoices_report/`.
   - **Verificar:** Se devuelve una respuesta 403 Forbidden; no se sirve ni formulario ni CSV.

4. **Caso borde — rango de fechas sin facturas anuladas:**
   - Enviar un rango de fechas en el futuro lejano (o cualquier rango sin facturas anuladas).
   - **Verificar:** Se descarga un CSV con solo la fila de encabezados y sin filas de datos.

5. **Caso borde — factura con múltiples ítems:**
   - Identificar una factura anulada con más de un `InvoiceItem`. Enviar un rango que la incluya.
   - **Verificar:** La fila del CSV para esa factura refleja correctamente los datos del `invoiceitem_set` prefetched sin ejecutar consultas adicionales (verificar con Django debug toolbar o `assertNumQueries` si está disponible).

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- Asegurarse de que los grupos `"Admins"` y `"Finances"` existan en el entorno destino; los usuarios que deban acceder al reporte deben ser miembros de al menos uno de ellos (o ser superusuarios).
- La vista `facturas_anuladas` heredada en `utopia-crm-ladiaria` puede retirarse después de que esta versión esté desplegada; su URL puede redirigirse a `canceled_invoices_report` o simplemente eliminarse.

## 🎓 Decisiones de Diseño

La vista se implementó como vista basada en clase (`TemplateView` + `UserPassesTestMixin`) en lugar de una vista de función para seguir el patrón usado por otras vistas de reporte y filtro agregadas recientemente a la app. `UserPassesTestMixin` proporciona un hook de control de acceso limpio y declarativo sin necesidad de un decorador o una verificación de permisos manual al inicio de cada método manejador.

Se eligió `prefetch_related` en lugar de `select_related` porque `invoiceitem_set` y `creditnote_set` son relaciones de FK inversa / M2M que no pueden unirse eficientemente con `select_related`. Dos consultas adicionales para cualquier conjunto de resultados es mucho mejor que una consulta por factura.

Se usaron date pickers nativos HTML5 para los inputs del formulario, de acuerdo con las pautas de UI del proyecto: usar `<input type="date">` cuando no se necesita comportamiento más sofisticado de picker, evitando cualquier dependencia adicional de JavaScript.

## 🚀 Mejoras Futuras

- Agregar validación del lado del servidor para el rango de fechas enviado (rechazar rangos invertidos o demasiado amplios) con un mensaje de error visible para el usuario.
- Considerar agregar un filtro por serie de factura o tipo de producto para permitir exportaciones más específicas.
- Agregar un toggle opcional de "incluir detalles de nota de crédito" para expandir las columnas de notas de crédito en el CSV.

---

- **Fecha:** 2026-04-08
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t0243
- **Tipo de cambio:** Funcionalidad
- **Módulos afectados:** Facturación
