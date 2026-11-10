# Las direcciones toman el país de su departamento

- **Fecha:** 2026-11-10
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#122
- **Tipo:** Corrección
- **Componente:** Core
- **Impacto:** Calidad de datos

## 🎯 Resumen

`Address.country` pasó a ser una clave foránea en la migración `0076`, que le puso país a todas las direcciones que existían en ese momento. Desde entonces, ninguno de los caminos que crean direcciones lo completa: el formulario de dirección nueva, las altas de MercadoPago y de Witty, el agregado de productos a un contacto. Sólo la importación de contactos por CSV lo intenta, por nombre. En la diaria había 13.966 direcciones sin país (13.555 con departamento). La ficha del contacto lo disimulaba, porque muestra el país a través del departamento (`address.state.country`), pero lo que lea `address.country` directo las dejaba afuera. Ahora una dirección que se guarda sin país toma el de su departamento, y una migración de datos completa las que ya existen de la misma forma.

## ✨ Cambios

### 1. `Address.save` toma el país del departamento

**Archivo:** `core/models.py`

```python
if self.country_id is None and self.state_id:
    self.country_id = self.state.country_id
```

Un departamento pertenece a un solo país, así que no es una suposición. No hay un país por defecto a ciegas: una dirección que trae su propio país (una dirección de facturación del exterior, por ejemplo) lo conserva, y una sin departamento sigue sin país.

### 2. Una migración de datos completa las que ya existen

**Archivo:** `core/migrations/0125_address_country_from_state.py`

La misma regla en un solo `UPDATE` con una subconsulta, sin llamar a `save()` por fila (eso dispararía la sincronización con la web en cada dirección). Las direcciones sin departamento quedan como están. Revertirla no hace nada.

## 📁 Archivos modificados

- **`core/models.py`** — `Address.save` toma el país del departamento
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos creados

- **`core/migrations/0125_address_country_from_state.py`** — Completa las direcciones existentes
- **`tests/test_address_country.py`** — Tests

## 🧪 Pruebas manuales

**Tests automatizados** (`tests/test_address_country.py`): el país sale del departamento, un país que viene con la dirección se conserva, sin departamento no hay país, y la migración completa las existentes y deja el resto. Pasa el suite completo del base (530 tests, sin `test_cmssync`, que necesita un CMS corriendo).

1. **Caso exitoso:**
   - Agregarle una dirección a un contacto desde la ficha, eligiendo un departamento.
   - **Verificar:** En el admin, la dirección tiene el país del departamento.

2. **Caso borde, sin departamento:**
   - Agregar una dirección sin departamento.
   - **Verificar:** Queda sin país, como antes.

## 📝 Notas de despliegue

- **Se requieren migraciones:** `core 0125`. En la diaria completa 13.555 direcciones en una sola consulta.
- Sin cambios de settings.

## 🎓 Decisiones de diseño

- **Del departamento, no de un país por defecto:** un valor por defecto le pondría el país local a direcciones del exterior; el departamento ya dice dónde está la dirección.
- **Una sola consulta, sin `save()` por fila:** guardar una dirección puede disparar la sincronización con la web.

---

- **Fecha:** 2026-11-10
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl122-pais-de-la-direccion
- **Tipo:** Corrección
- **Módulos afectados:** core
