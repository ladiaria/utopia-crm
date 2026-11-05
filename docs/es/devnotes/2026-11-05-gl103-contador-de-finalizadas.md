# El CSV de deudores cuenta bien las incidencias finalizadas

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#103
- **Tipo:** Corrección de error
- **Componente:** Modelos de core, Support
- **Impacto:** Reportes

## 🎯 Resumen

`Contact.get_finished_issues_by_category_count` tenía la misma consulta que su par de abiertas, así que la columna «Finished invoicing issues» del CSV de deudores mostraba las abiertas, con el mismo número que la columna de al lado. Ahora cuenta las incidencias en un estado terminal.

## ✨ Cambios

### 1. El contador

**Archivo:** `core/models.py`

```python
return self.issue_set.filter(category=category, status__is_terminal=True).count()
```

### 2. Se va el contador sin uso

**Archivo:** `core/models.py`

`get_finished_issues_by_subcategory_count` tenía el mismo error y nada lo usaba, así que se saca en vez de corregirlo.

## 📁 Archivos Modificados

- **`core/models.py`** — Los dos contadores
- **`tests/test_debtor_contacts.py`** — Los contadores y las columnas del CSV

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - Exportá el CSV de deudores de un deudor con incidencias de facturación abiertas y cerradas.
   - **Verificar:** Cada columna muestra su propio número.

2. **Caso borde, otra categoría:**
   - Cerrá una incidencia de otra categoría del mismo contacto.
   - **Verificar:** No cuenta en la columna de finalizadas.

## 📝 Notas de Despliegue

No se requieren migraciones. El número de esa columna cambia, así que conviene avisarle a quien use ese CSV.

---

- **Fecha:** 2026-11-05
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl103-contador-finalizadas
- **Tipo:** Corrección de error
- **Módulos afectados:** core, tests
