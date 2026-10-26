# La consola del vendedor lista más de una subcategoría de "nunca pagó"

- **Fecha:** 2026-10-26
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl60-consola-vendedor-no-consolidados
- **Tipo:** Mejora
- **Componente:** Support (consola del vendedor)
- **Impacto:** Experiencia de usuario

## 🎯 Resumen

La consola del vendedor lista las incidencias abiertas de la subcategoría `ISSUE_SUBCATEGORY_NEVER_PAID` asignadas al
vendedor, y las cuenta en la lista de campañas. la diaria partió "nunca pagó" en variantes, como una para los
contactos que deben 2 facturas o más en la misma suscripción: cuando una incidencia pasaba a una variante,
desaparecía de la consola aunque siguiera asignada al vendedor. Con el setting nuevo y opcional
`ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS`, esas subcategorías también se listan y se cuentan
(it/utopia-crm-ladiaria#60). Se mergeó en el PR #399; esta entrada se agregó después.

## ✨ Cambios

### 1. `get_never_paid_subcategory_slugs()`

**Archivo:** `support/views/seller_console.py`

Devuelve `ISSUE_SUBCATEGORY_NEVER_PAID` más `ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS`, o una lista vacía si el
primero no está cargado. Las dos vistas de la consola la usan, y un paquete que pise `seller_console_list_campaigns`
puede importarla para contar las mismas incidencias.

### 2. Página de "nunca pagó" y conteo en la lista de campañas

**Archivos:** `support/views/seller_console.py`, `support/templates/seller_console_never_paid_issues.html`

Las dos filtran con `sub_category__slug__in`. Con más de una subcategoría, la página muestra una columna Subcategoría
(el texto ya estaba traducido); con una sola, la columna repetiría el mismo valor en todas las filas, así que no se
muestra.

### 3. Setting

**Archivo:** `local_settings_sample.py`

`ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS`, comentado, con su explicación. Se lee con `getattr`, así que no tiene
valor por defecto en `settings.py`, igual que `ISSUE_SUBCATEGORY_NEVER_PAID`.

## 📁 Archivos Modificados

- **`support/views/seller_console.py`** — `get_never_paid_subcategory_slugs()` y su uso en las dos vistas.
- **`support/templates/seller_console_never_paid_issues.html`** — Columna Subcategoría opcional.
- **`local_settings_sample.py`** — El setting nuevo.

## 📁 Archivos Creados

- **`tests/test_seller_console_never_paid.py`** — 6 tests: la lista de slugs con y sin extras o sin el setting base,
  la página con las dos subcategorías (y sin otras subcategorías, incidencias terminadas ni de otros vendedores), la
  columna oculta y el conteo en la lista de campañas.

## 🧪 Pruebas Manuales

1. **Variante listada (camino feliz):**
   - Cargar `ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS` con el slug de una variante. Asignarle al vendedor una
     incidencia abierta de cada subcategoría.
   - Abrir la consola del vendedor y después su página de "nunca pagó".
   - **Verificar:** el conteo es 2, se listan las dos incidencias y la columna Subcategoría las distingue.

2. **Sin el setting:**
   - Sacarlo.
   - **Verificar:** sólo se lista la incidencia de `ISSUE_SUBCATEGORY_NEVER_PAID`, sin la columna Subcategoría.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- Cargar `ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS` en `local_settings.py` donde se quiera.
- Un paquete que importe `get_never_paid_subcategory_slugs` necesita este cambio deployado antes.

---

- **Fecha:** 2026-10-26
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl60-consola-vendedor-no-consolidados
- **Tipo de cambio:** Mejora
- **Módulos afectados:** Support
