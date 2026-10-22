# CSV legible para el cierre de agendas perdidas

- **Fecha:** 2026-10-22
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl57-csv-legible (it/utopia-crm-ladiaria#57)
- **Tipo:** Mejora de UX
- **Componente:** Core (campañas)
- **Impacto:** Auditoría, Operación

## 🎯 Resumen

`close_lost_schedule_activities --csv` escribe la lista de agendas que va a cerrar, para que alguien la audite antes
de correrlo de verdad. Ese alguien no suele ser un desarrollador, y el CSV salía con los códigos crudos (`3`, `5`,
`NF`, `LS`) y en un orden que intercalaba el antes y el después, así que una fila parecía decir que el contacto ya
estaba cerrado. Para el corte del 2026-07-31, la diaria tuvo que armar a mano una versión legible con un script
aparte. Este cambio hace que el comando genere esa versión solo: etiquetas de los choices en vez de códigos,
encabezado traducido, "hoy" agrupado antes de "después del cierre", dos columnas más para auditar y un archivo que
Excel abre con los acentos bien. El resumen por consola también pasa de números fijos a etiquetas.

## ✨ Cambios

### 1. Etiquetas en vez de códigos

**Archivo:** `core/management/commands/close_lost_schedule_activities.py`

Las columnas de estado usan `CAMPAIGN_STATUS(valor).label` y las de resolución `CAMPAIGN_RESOLUTION_CHOICES`. Las dos
pasan por `gettext`, así que el CSV sale en el `LANGUAGE_CODE` de la instalación. Las etiquetas son lazy, así que se
pasan a `str` antes de unirlas o escribirlas.

- Un estado de campaña sin resolución muestra `(sin resolución)`.
- Una agenda sin `ContactCampaignStatus` deja vacías las cuatro columnas de estado y resolución.

### 2. Orden de columnas y encabezado traducido

**Archivo:** `core/management/commands/close_lost_schedule_activities.py`

`CSV_HEADER` pasó a ser `CSV_COLUMNS`, en este orden:

```text
Fecha de la agenda, Vendedor, Vendedor interno, Campaña, Campaña activa, ID de contacto, Contacto,
Estado hoy, Resolución hoy, Estado después del cierre, Resolución después del cierre, ID de actividad
```

La fila de encabezado se escribe desde `csv_header()`, que traduce cada columna en el momento de escribir.

### 3. Dos columnas para auditar

**Archivo:** `core/management/commands/close_lost_schedule_activities.py`

- **Vendedor interno** (`Seller.internal`): en la diaria separa las agendas de vendedores que siguen trabajando de
  las que quedaron de gente que ya no está. En el corte del 2026-07-31 fueron 119 de 318.
- **Campaña activa** (`Campaign.active`).

Las dos se escriben como "Sí" / "No" traducidos.

### 4. Archivo para Excel

**Archivo:** `core/management/commands/close_lost_schedule_activities.py`

El archivo se escribe con `encoding="utf-8-sig"`. El BOM es lo que le dice a Excel que el archivo es UTF-8; sin él,
los acentos de las etiquetas salen rotos.

### 5. El resumen por consola con etiquetas

**Archivo:** `core/management/commands/close_lost_schedule_activities.py`

Las dos líneas de transiciones estaban fijas en el código (`Status 2/6/7 -> 4 (ended with contact), resolution LS`).
Ahora `print_transitions()` arma una línea por estado terminal a partir de `STATUS_MAP`, con etiquetas:

```text
  - Contactado, Pasar a la mañana, Pasar a la tarde -> Finalizado con contacto (Finalizado por agenda perdida): 227
  - No se contactó aún, Llamado, no se pudo contactar -> Finalizado sin contacto (Finalizado por agenda perdida): 91
```

## 📁 Archivos Modificados

- **`core/management/commands/close_lost_schedule_activities.py`** — Etiquetas, orden de columnas, encabezado
  traducido, dos columnas nuevas, `utf-8-sig`, resumen desde `STATUS_MAP`.
- **`locale/es/LC_MESSAGES/django.po`** — Nueve msgid nuevos: las columnas nuevas del encabezado y
  `(no resolution)`.
- **`tests/test_close_lost_schedule.py`** — Nuevo `CloseLostScheduleCsvTest` (6 tests).
- **`CHANGELOG.md`** — Entrada de este cambio.

## 📚 Detalles Técnicos

- Los tests comparan contra las etiquetas de los choices y no contra un texto fijo: corren en `en-us`, y producción
  escribe en castellano.
- Cambiaron las columnas del CSV. Lo que leyera el CSV viejo por nombre de columna se rompe, pero nada en los repos lo
  hace: es para personas.

## 🧪 Pruebas Manuales

1. **El corte del 2026-07-31 contra un dump de producción (camino feliz):**
   - Correr `python manage.py close_lost_schedule_activities --date 2026-07-31 --dry-run --csv /tmp/agendas.csv` con
     `LANGUAGE_CODE = "es"` y las traducciones compiladas.
   - **Verificar:** encabezado en castellano, etiquetas en las cuatro columnas de estado, "Sí"/"No" en las dos
     columnas nuevas. Hecho contra el dump del 2026-10-08: 318 filas, idéntico a la versión armada a mano.

2. **Abrirlo en Excel:**
   - Abrir el CSV con doble clic.
   - **Verificar:** los acentos se leen bien ("Resolución", "Campaña").

3. **Agenda sin estado de campaña (caso borde):**
   - Crear una agenda pendiente con campaña y sin `ContactCampaignStatus`, y correr el comando con `--csv`.
   - **Verificar:** la fila está, con sus cuatro columnas de estado y resolución vacías, y el resumen la informa en
     "Without ContactCampaignStatus".

## 📝 Notas de Despliegue

- No se requieren migraciones.
- **Recompilar traducciones** (`python manage.py compilemessages -l es`): sin eso el encabezado sale en inglés.

---

- **Fecha:** 2026-10-22
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl57-csv-legible
- **Tipo de cambio:** Mejora de UX
- **Módulos afectados:** Core
