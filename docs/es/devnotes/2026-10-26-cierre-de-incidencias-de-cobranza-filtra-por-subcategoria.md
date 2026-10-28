# El cierre automático nocturno de incidencias de facturación vuelve a cerrar

- **Fecha:** 2026-10-26
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl63-close-invoicing-issues-subcategorias
- **Tipo:** Corrección de error
- **Componente:** Support (comando `close_invoicing_issues`)
- **Impacto:** Integridad de datos, lógica de negocio

## 🎯 Resumen

`close_invoicing_issues` cierra las incidencias de facturación abiertas de los contactos que ya no son deudores.
Comparaba la lista `ISSUE_SUBCATEGORY_AUTO_CLOSE_SLUGS` contra el **estado** de la incidencia en vez de su
subcategoría, así que con los dos settings de cierre automático cargados el queryset quedaba siempre vacío y el comando
no cerraba nada. Corregir el filtro no alcanzaba: un contacto también deja de ser deudor cuando sus facturas vencidas
se marcan como incobrables, y esas incidencias se habrían cerrado como "resueltas, facturas pagas" sin que hubiera
pago. Ahora el comando mira la última factura saldada del contacto: si está paga o debitada, cierra la incidencia como
resuelta, como antes; si es incobrable, la cierra con el estado del setting nuevo `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE`,
o la deja abierta si el setting no está. Lo encontró la diaria (it/utopia-crm-ladiaria#63).

## ✨ Cambios

### 1. Las subcategorías se filtran por subcategoría

**Archivo:** `support/management/commands/close_invoicing_issues.py`

```python
issues = issues.filter(sub_category__slug__in=issue_subcat_autoclose)  # antes status__slug__in
```

### 2. Pago o incobrable: la última factura saldada

**Archivo:** `support/management/commands/close_invoicing_issues.py`

Para un contacto que ya no es deudor (`Contact.is_debtor()`, que no cuenta las facturas incobrables),
`last_settled_invoice()` devuelve la última factura no anulada que está paga, debitada o incobrable:

- **Paga o debitada:** `mark_solved()` con la misma nota que antes.
- **Incobrable:** con `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE` cargado, la incidencia pasa a ese estado, con fecha de
  cierre de hoy y una nota en `answer_2` que dice que las facturas vencidas se marcaron como incobrables. Sin el
  setting, la incidencia queda abierta.
- **Ninguna:** la incidencia queda abierta.

Una factura pendiente que todavía no venció no se mira: es un ciclo de facturación nuevo y no dice cómo terminó la
deuda de la incidencia.

### 3. Setting `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE`

**Archivos:** `settings.py`, `local_settings_sample.py`

Por defecto es `None`. Tiene que ser el slug de un estado terminal (por ejemplo `not-solved`).

### 4. `--dry-run`

**Archivo:** `support/management/commands/close_invoicing_issues.py`

Muestra qué cerraría, y cómo, sin guardar nada. La primera corrida después de este arreglo puede cerrar de una vez
todo lo que se acumuló mientras el comando no hacía nada.

### 5. Traducciones

**Archivo:** `locale/es/LC_MESSAGES/django.po`

Los mensajes ahora se traducen con `gettext` y el `.format()` va afuera de la llamada (antes el msgid era el texto ya
formateado, así que nunca coincidía). Dos textos nuevos en español. Se sacó `DEFAULT_NOTE`, que no se usaba.

## 📁 Archivos Modificados

- **`support/management/commands/close_invoicing_issues.py`** — Filtro por subcategoría, última factura saldada,
  cierre de incobrables, `--dry-run`.
- **`settings.py`** — `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE`, `None` por defecto.
- **`local_settings_sample.py`** — El setting, comentado, con su explicación.
- **`locale/es/LC_MESSAGES/django.po`** — Español de los mensajes nuevos.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 📁 Archivos Creados

- **`tests/test_close_invoicing_issues.py`** — 8 tests: pagó, incobrable con y sin el setting, pagó después de una
  deuda incobrable vieja, pendiente sin vencer, sigue siendo deudor, otra subcategoría u otro estado, y `--dry-run`.

## 🎓 Decisiones de Diseño

- **La última factura saldada, no "tiene alguna factura incobrable".** Un contacto con deuda incobrable de hace años
  que después pagó todo sí pagó: su incidencia está resuelta.
- **Las incidencias incobrables se cierran, no se reabren ni quedan colgadas.** Una vez que la deuda se da por perdida
  no queda nada por hacer con la incidencia, así que cuenta como cerrada, pero no como resuelta. El estado es
  configurable porque cada instalación nombra sus estados distinto.
- **El estado de incobrables es opcional.** Sin el setting, una instalación conserva el comportamiento que se buscaba
  antes para quienes pagan, y a la deuda dada por perdida no le pasa nada nuevo.

## 🧪 Pruebas Manuales

1. **Contacto que pagó (camino feliz):**
   - Incidencia de facturación abierta en un estado y una subcategoría de cierre automático; marcar la factura vencida
     del contacto como paga sin pasar por el flujo de pago que ya cierra incidencias.
   - Correr `python manage.py close_invoicing_issues --dry-run` y después sin la opción.
   - **Verificar:** el dry run lista la incidencia como paga y no cambia nada; la corrida real la deja resuelta con la
     nota "cerrada automáticamente por pago de facturas".

2. **Deuda dada por perdida:**
   - Cargar `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE`. Marcar como incobrables las facturas vencidas del contacto.
   - Correr el comando.
   - **Verificar:** la incidencia tiene ese estado, fecha de cierre de hoy y la nota de incobrables.

3. **Deuda dada por perdida, sin el setting:**
   - Igual que el anterior, sin el setting.
   - **Verificar:** la incidencia queda abierta.

4. **Ciclo nuevo pendiente:**
   - El contacto pagó la factura de la incidencia y tiene una factura nueva que vence la semana que viene.
   - **Verificar:** la incidencia se cierra como resuelta.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- Compilar traducciones: `python manage.py compilemessages -l es`.
- Cargar `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE` en `local_settings.py` si se quiere cerrar la deuda dada por perdida.
- Antes de la primera corrida del cron, correr `python manage.py close_invoicing_issues --dry-run` y revisar cuántas
  incidencias cerraría: lo acumulado de todos los días en que el comando no hizo nada se cierra de una vez.

---

- **Fecha:** 2026-10-26
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl63-close-invoicing-issues-subcategorias
- **Tipo de cambio:** Corrección de error
- **Módulos afectados:** Support
