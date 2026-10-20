# Filtros de campañas en la lista de asignación a vendedores

- **Fecha:** 2026-10-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** assign-sellers-filters
- **Tipo:** Mejora
- **Componente:** Support (gestión de campañas)
- **Impacto:** Experiencia del call center, Rendimiento

## 🎯 Resumen

La página "Asignar contactos a vendedores" (`/support/assign_sellers/`) listaba todas las campañas con al menos un
contacto sin vendedor, incluidas cientos de campañas viejas e inactivas. Ahora muestra por defecto sólo las campañas
activas, se puede filtrar por nombre y muestra el estado y las fechas de cada campaña. Los conteos se calculan en
una sola consulta en vez de tres consultas por campaña.

## ✨ Cambios

### 1. Filtros de activa y nombre, con activa por defecto

**Archivo:** `support/views/all_views.py`

`list_campaigns_with_no_seller` reusa el `CampaignFilter` existente (el mismo que usa la página de estadísticas de
campañas), así que las dos páginas comparten el mismo formulario de filtro. Cuando el pedido no trae `active`, la
vista aplica `active=true`:

```python
filter_data = request.GET.copy()
filter_data.setdefault("active", "true")
```

Elegir "Desconocido" en el select muestra todas las campañas; "No" muestra sólo las inactivas.

### 2. Conteos anotados en una sola consulta

La versión anterior hacía tres consultas `count()` por campaña (sin asignar, mañana, tarde). Con unas 300 campañas
en local, eran unas 900 consultas. Ahora los conteos son anotaciones `Count(..., filter=Q(...))`, y la condición
"tiene contactos sin vendedor" es una subconsulta `Exists`, para que no interfiera con los joins de los conteos.
La página entera hace ahora 7 consultas. Los resultados se ordenan primero las activas y después por nombre.

### 3. Columnas de estado y fechas

**Archivo:** `support/templates/distribute_campaigns.html`

- Columnas nuevas: **Estado** (badge verde "Activa" / gris "Inactiva"), **Fecha de comienzo** y **Fecha de fin**.
- Card de filtros arriba de la tabla, con un botón "Limpiar" que vuelve a la vista por defecto.
- El nombre de la campaña ahora enlaza a la página de asignación con `{% url %}` en vez de un `href` relativo.
- Una fila vacía dice "No se encontraron campañas" cuando los filtros no encuentran nada.

### 4. Traducciones con contexto

**Archivo:** `locale/es/LC_MESSAGES/django.po`

"Campaña" es femenino y las traducciones existentes de "Active"/"Inactive" son masculinas. Los badges usan
`{% trans "Active" context "campaign" %}`, con entradas nuevas `msgctxt "campaign"` ("Activa"/"Inactiva"). Se
agregó además "No campaigns found".

## 📁 Archivos modificados

- **`support/views/all_views.py`** — Filtro con activa por defecto, conteos anotados.
- **`support/templates/distribute_campaigns.html`** — Formulario de filtro, columnas de estado y fechas, estado vacío.
- **`locale/es/LC_MESSAGES/django.po`** — Textos nuevos.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 🧪 Pruebas manuales

1. **Vista por defecto (camino feliz):**
   - Abrir `/support/assign_sellers/`.
   - **Verificar:** sólo aparecen campañas activas, cada una con badge verde y sus fechas.

2. **Todas las campañas e inactivas:**
   - Poner "Activo" en "Desconocido" y filtrar; después en "No".
   - **Verificar:** lo primero muestra todas las campañas, lo segundo sólo las inactivas (badge gris).

3. **Filtro por nombre sin resultados (caso borde):**
   - Escribir un nombre que no existe y filtrar.
   - **Verificar:** la tabla muestra "No se encontraron campañas"; "Limpiar" vuelve a las campañas activas.

4. **Conteos sin cambios:**
   - Comparar las columnas Contactos / Mañana / Tarde con la página de asignación de una campaña.
   - **Verificar:** coinciden (comprobado en local contra el cálculo viejo en 232 campañas, sin diferencias).

## 📝 Notas de despliegue

- No se requieren migraciones.
- **Recompilar traducciones** (`python manage.py compilemessages -l es`).
- Sin cambios de configuración.

## 🎓 Decisiones de diseño

- **Activa por defecto, no fija.** Una campaña inactiva puede seguir teniendo contactos esperando vendedor, así que
  sigue siendo accesible desde el filtro en vez de quedar excluida.
- **Reusar `CampaignFilter`** mantiene el filtro consistente con la página de estadísticas de campañas.

---

- **Fecha:** 2026-10-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** assign-sellers-filters
- **Tipo:** Mejora
- **Módulos afectados:** Support
