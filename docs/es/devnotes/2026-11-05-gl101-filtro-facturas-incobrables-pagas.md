# Filtro de facturas: incobrables pagas o debitadas

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#101
- **Tipo:** Mejora
- **Componente:** Facturación
- **Impacto:** Reportes

## 🎯 Resumen

El filtro de estado de la lista de facturas admite una sola opción, así que no había forma de encontrar las facturas dadas por incobrables que igual se cobraron. Una opción nueva lo resuelve, y deja afuera las anuladas, porque esa plata puede no haber quedado.

## ✨ Cambios

### 1. Opción nueva de estado

**Archivo:** `invoicing/filters.py`

```python
queryset.filter(Q(paid=True) | Q(debited=True), uncollectible=True, canceled=False)
```

La opción «Incobrable» no cambia: sigue trayendo todas.

## 📁 Archivos Modificados

- **`invoicing/filters.py`** — La opción nueva
- **`locale/es/LC_MESSAGES/django.po`** — Su traducción

## 📁 Archivos Creados

- **`tests/test_invoice_filter_uncollectible.py`** — Qué trae y qué deja afuera la opción

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - En la lista de facturas, elegí «Incobrable, pago o debitado» como estado.
   - **Verificar:** Cada factura es incobrable y está paga o debitada, y el total de arriba las suma.

2. **Caso borde, anuladas:**
   - Tomá una factura incobrable que se pagó y después se anuló.
   - **Verificar:** No aparece con esta opción, y sí aparece con «Incobrable».

## 📝 Notas de Despliegue

No se requieren migraciones. El server compila la traducción.

---

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl101-filtro-incobrables-pagas
- **Tipo:** Mejora
- **Módulos afectados:** invoicing
