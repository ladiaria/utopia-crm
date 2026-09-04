# Cierre de agendas perdidas con una resolución de campaña propia

- **Fecha:** 2026-09-04
- **Autor:** Tanya Tree + Claude Opus 5
- **Ticket:** t1175
- **Tipo:** Funcionalidad (+ Corrección sobre el comando que reemplaza)
- **Componente:** Core — Campañas, Actividades, Acciones de la consola de vendedores; Support —
  Consola de vendedores
- **Impacto:** Integridad de Datos, Estadísticas de Campañas, Colas de la Consola

## 🎯 Resumen

Gestión de comunidad pidió cerrar todas las **agendas** colgadas —una `Activity` pendiente de tipo
llamada asociada a una campaña, que es como la consola de vendedores representa "volver a llamar a
este contacto tal día"— anteriores al 2026-05-31, y cerrar también el `ContactCampaignStatus`
asociado dejando marcado que el cierre fue forzado y no obra de un vendedor.

Las agendas colgadas no son sólo ruido. Un contacto con una actividad pendiente queda para siempre en
la cola "act" de la consola, se sigue contando en el trabajo pendiente del vendedor y —lo caro— queda
excluido de la cola "new" de **todas** las campañas activas, vía `Campaign.get_not_contacted()`. Una
agenda de 2025 bloquea a ese contacto para cualquier campaña que corra hoy. En producción hay 1.173
actividades de este tipo, repartidas en 1.167 pares contacto/campaña.

El cambio agrega un valor nuevo de `campaign_resolution` (`LS`, *finalizado por agenda perdida*), un
comando nuevo `close_lost_schedule_activities`, y una acción de consola `close-lost-schedule` que
marca el cierre forzado. Además reemplaza a
`close_old_pending_activities_and_campaign_status`, que hacía el mismo trabajo de forma destructiva:
forzaba **cualquier** estado de campaña a `5` / `CW` sin mirar lo que ya estaba resuelto, y cuando se
corrió en producción el 2025-07-01 pisó 181 ventas exitosas.

## ✨ Cambios

### 1. Una resolución de campaña nueva, no un status nuevo

**Archivo:** `core/choices.py`

La etiqueta del cierre forzado vive en `campaign_resolution` —el campo que dice *por qué* terminó
así un contacto— y no en `status`, que dice *en qué punto del embudo* quedó:

```python
CAMPAIGN_RESOLUTION_CHOICES = (
    ...
    ("CW", _("Close without contact")),
    ("LS", _("Closed due to lost schedule")),
)
```

El 96,3% de las agendas colgadas cuelga de un contacto en `status=2` (contactado): la agenda se pactó
hablando con la persona. Un valor nuevo de `status` los sacaría a todos de `get_contacted_statuses()`,
con lo cual gente con la que **sí** se habló aparecería en el CSV de "inubicables"
(`not_contacted_campaign`) y engordaría el denominador de `unreachable_pct` y
`error_in_promotion_pct` en todo el histórico de esas campañas. Un código de resolución nuevo, en
cambio, no cae en ningún balde de las estadísticas: aparece en los filtros, en los exports y en el
glosario de la API de actividades, y nada más. El precedente es `NF`, agregado exactamente así en
`core.0117`.

### 2. El status de campaña se mapea condicionalmente

**Archivo:** `core/management/commands/close_lost_schedule_activities.py`

En vez de mandar todo a "finalizado sin contacto", el status terminal respeta lo que ya se sabía del
contacto:

```python
STATUS_MAP = {
    CAMPAIGN_STATUS.NOT_YET_CONTACTED: CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
    CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT: CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
    CAMPAIGN_STATUS.CONTACTED: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
    CAMPAIGN_STATUS.SWITCH_TO_MORNING: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
    CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
}
```

Los status 4 y 5 ya son terminales y no están en el mapa, así que no se tocan; la actividad colgada
igual se cierra. Las ventas están protegidas aparte: un estado con resolución `S1` o `S2` nunca se
sobrescribe, sea cual sea su status.

### 3. El cierre forzado queda legible en tres lugares

**Archivos:** `core/management/commands/close_lost_schedule_activities.py`,
`core/management/commands/populate_seller_console_actions.py`

1. `ContactCampaignStatus.campaign_resolution = "LS"` — la resolución misma.
2. `Activity.seller_console_action` → la acción nueva `close-lost-schedule`, que es lo que distingue
   este cierre del `close-without-contact` que un vendedor aprieta a mano. La misma acción queda en
   `ContactCampaignStatus.last_console_action`.
3. `Activity.notes` — se **appendea** una línea fechada, sin pisar nunca lo que ya había:
   *"Cerrado automáticamente por agenda perdida (t1175, 2026-09-04)."*

La acción tuvo que ir a la tupla de `populate_seller_console_actions`: ese comando **borra** toda
`SellerConsoleAction` que no esté en ella, y tanto `Activity.seller_console_action` como
`ContactCampaignStatus.last_console_action` son `on_delete=SET_NULL` — crear la acción a mano
significaría que la marca desaparece en silencio de miles de filas la próxima vez que alguien corra
el populate.

Pero la tupla forzaba `is_active=True`, y `get_seller_console_action()` filtra por `is_active=True`.
Por eso la tupla creció una sexta columna y la acción nueva queda registrada **inactiva**: sobrevive
al populate y no se puede disparar desde la consola con un POST armado a mano.

```python
(
    SellerConsoleAction.ACTION_TYPES.NO_CONTACT,
    "close-lost-schedule",
    "Cerrado por agenda perdida",
    None,  # El status lo decide por contacto close_lost_schedule_activities
    "LS",  # Closed due to lost schedule
    False,
),
```

### 4. El comando

**Archivo:** `core/management/commands/close_lost_schedule_activities.py`

```bash
python manage.py close_lost_schedule_activities --date 2026-05-31 --dry-run --csv /tmp/lost.csv
python manage.py close_lost_schedule_activities --date 2026-05-31
```

| Flag | Obligatorio | Para qué |
| --- | --- | --- |
| `--date YYYY-MM-DD` | sí | Cierra agendas de esa fecha o anteriores. Sin default a propósito: nadie debe cerrar agendas por accidente |
| `--dry-run` | no | No escribe nada; imprime el desglose completo de transiciones |
| `--csv RUTA` | no | Vuelca las filas afectadas (contacto, campaña, vendedor, fecha de la agenda, status y resolución antes/después) para auditar antes de ejecutar |
| `--campaign ID` | no | Acota a una campaña, para hacerlo por tandas |
| `--limit N` | no | Corta el universo, para una primera pasada chica |

La selección es deliberadamente angosta: `status` en `P`/`E`, `activity_type="C"`,
`campaign__isnull=False`. Las actividades pendientes sin campaña quedan fuera del alcance del ticket,
y sólo las llamadas funcionan como agenda en la consola. Se incluye `EXPIRED` aunque hoy no haya
ninguna fila así, por si `expire_old_pending_activities` empieza a correr.

La fecha incluye el día entero, que es lo que pidió gestión de comunidad:

```python
cutoff = datetime.combine(parsed, time.max)
return timezone.make_aware(cutoff) if settings.USE_TZ else cutoff
```

### 5. El comando viejo pasa a ser un stub

**Archivo:** `core/management/commands/close_old_pending_activities_and_campaign_status.py`

`close_old_pending_activities_and_campaign_status` seteaba `status=5` y `campaign_resolution="CW"`
sobre *cualquier* `ContactCampaignStatus` del par, ventas incluidas. Se corrió en producción el
2025-07-01 (7.927 actividades, 7.768 estados a `CW`) y pisó **181** ventas exitosas — las 181 tienen
una suscripción con `start_date` anterior a la corrida, o sea que la venta ya existía cuando se
borró.

No está en ningún crontab (`ss_conf/etc/cron.d/crm`), así que nada depende de su comportamiento
actual. En vez de dejar un arma cargada al lado de su gemelo arreglado, ahora aborta:

```python
raise CommandError(
    "This command is deprecated because it overwrote already resolved campaign statuses, sales "
    "included. Use 'close_lost_schedule_activities' instead:\n"
    "    python manage.py close_lost_schedule_activities --date YYYY-MM-DD --dry-run"
)
```

Es un stub y no un recableado silencioso: quien lo tenga en un runbook personal recibe un mensaje
claro en vez de una semántica distinta sin enterarse.

## 📁 Archivos Creados

- **`core/management/commands/close_lost_schedule_activities.py`** — El comando
- **`core/migrations/0122_add_lost_schedule_campaign_resolution.py`** — `AlterField` sobre
  `ContactCampaignStatus.campaign_resolution`
- **`support/migrations/0041_add_lost_schedule_campaign_resolution.py`** — `AlterField` sobre
  `SellerConsoleAction.campaign_resolution`
- **`tests/test_close_lost_schedule.py`** — 19 tests

## 📁 Archivos Modificados

- **`core/choices.py`** — Valor `LS` nuevo en `CAMPAIGN_RESOLUTION_CHOICES`
- **`core/management/commands/populate_seller_console_actions.py`** — Sexta columna `is_active` en la
  tupla; `close-lost-schedule` registrada inactiva
- **`core/management/commands/close_old_pending_activities_and_campaign_status.py`** — Reducido a un
  stub que aborta
- **`COMMANDS.md`** — Fila nueva para el comando; la vieja marcada `deprecated`
- **`locale/es/LC_MESSAGES/django.po`** — Dos cadenas nuevas: la etiqueta de la resolución y la nota
  de la actividad

## 📚 Detalles Técnicos

### Por qué `bulk_update` y no `save()`

`ContactCampaignStatus.last_action_date` es `auto_now=True`. Con `save()`, todas las filas tocadas
pasarían a decir "última acción: hoy", pisando la fecha de la última acción **real** y rompiendo los
filtros `last_action_date_min/max` de `ContactCampaignStatusFilter`. `bulk_update` sólo escribe los
campos que se le pasan, así que `last_action_date` queda como está. La fecha del cierre forzado se lee
de la nota de la actividad y de la resolución `LS`.

La contrapartida asumida: `Activity` tiene `HistoricalRecords` y `bulk_update` no dispara señales, así
que no quedan filas de historial del cierre. La trazabilidad ya vive en la propia fila (la acción
`close-lost-schedule` más la nota fechada) y en el CSV que se guarda del dry run; un historial
sintético de miles de filas no agregaría nada.

### Forma de las consultas

Los pares se resuelven en una sola query y se guardan en un dict `{(contact_id, campaign_id): ccs}` —
nunca una query por actividad. Un par con más de una agenda colgada (6 en producción) cierra las dos
actividades pero mapea el estado de campaña una sola vez.

### `USE_TZ`

Esta instalación corre con `USE_TZ = False` (el default de Django 4), donde `timezone.now()` devuelve
un datetime naive y `timezone.localdate()` explota. El comando arma el corte con `make_aware` sólo
cuando `settings.USE_TZ` está encendido, así sigue sirviendo en instalaciones del repo base que lo
tengan activo.

### Lo que deliberadamente no se toca

- **`ContactCampaignStatus.seller`** — nullearlo mandaría esos contactos al balde "sin vendedor" de
  `AssignSellerView`, que es lo contrario de cerrarlos, y rompería `campaign_statistics_per_seller`.
- **`Activity.datetime`** — la fecha pactada es información. (El cierre manual desde la consola sí la
  pisa con `now()`; este no.)
- **`resolution_reason`** — es la lista de motivos de rechazo de `local_settings`; una agenda perdida
  no es un rechazo.
- **Suscripciones y `Campaign.active`** — fuera de alcance.

## 🧪 Pruebas Manuales

1. **Caso exitoso — se cierra una agenda de un contacto contactado:**
   - Correr `python manage.py populate_seller_console_actions`.
   - Elegir un contacto con una actividad de llamada pendiente anterior al corte, cuyo
     `ContactCampaignStatus` esté en status 2 con resolución `SC`.
   - Correr `python manage.py close_lost_schedule_activities --date 2026-05-31 --dry-run` y leer el
     desglose; después correrlo sin `--dry-run`.
   - **Verificar:** la actividad queda `Completada` con la acción `close-lost-schedule` y una nota
     appendeada debajo de la original; el estado de campaña queda en 4 (finalizado con contacto) con
     resolución `LS`; el contacto ya no aparece en la cola "act" de la consola; su
     `last_action_date` no cambió.

2. **Caso borde — un estado que ya tiene una venta:**
   - Elegir un par cuyo `ContactCampaignStatus` tenga resolución `S1` o `S2` y una agenda colgada.
   - Correr el comando.
   - **Verificar:** la actividad se cierra, pero el estado de campaña conserva su status y su
     resolución `S1`/`S2`. Es exactamente la falla del comando viejo.

3. **Caso borde — la fecha de corte es inclusive:**
   - Crear dos agendas, una el 2026-05-31 23:30 y otra el 2026-06-01 09:00.
   - Correr con `--date 2026-05-31`.
   - **Verificar:** la primera se cierra, la segunda no se toca.

4. **Caso borde — agenda huérfana:**
   - Elegir una actividad con campaña pero sin `ContactCampaignStatus` (hay 2 en producción).
   - Correr el comando.
   - **Verificar:** la actividad se cierra y el par aparece en el resumen bajo "Without
     ContactCampaignStatus".

5. **Idempotencia:**
   - Correr el comando dos veces con la misma fecha.
   - **Verificar:** la segunda corrida informa "No schedules to close with the given parameters."

### Tests automáticos

```bash
python -W ignore manage.py test --settings=test_settings --keepdb tests.test_close_lost_schedule
```

19 tests que cubren el mapeo de cada status, la protección de las ventas, el corte inclusive, las
actividades sin campaña, las actividades que no son llamadas, los pares con dos agendas, las agendas
huérfanas, `--dry-run`, `--campaign`, la idempotencia, `last_action_date`, el guardarraíl de
`get_contacted_statuses()`, la falta de la acción de consola, el comando deprecado, y el hecho de que
`close-lost-schedule` sobrevive al populate quedando inactiva.

## 📝 Notas de Despliegue

- **Se requieren migraciones:** `core.0122` y `support.0041`. Las dos son `AlterField` sólo de
  choices, así que a nivel de base de datos son no-ops en PostgreSQL.
- **Hay que correr `populate_seller_console_actions` después de migrar.** Sin eso el comando aborta,
  porque la acción `close-lost-schedule` no existe.
- Hace falta `compilemessages` para la etiqueta en español ("Finalizado por agenda perdida") y para la
  nota de la actividad; el archivo `.mo` no está versionado.
- La corrida es una decisión separada del deploy. Orden recomendado en producción:

  ```bash
  python manage.py migrate
  python manage.py populate_seller_console_actions
  python manage.py close_lost_schedule_activities --date 2026-05-31 --dry-run \
      --csv /tmp/lost_schedules_t1175.csv
  # pasarle el CSV y el resumen a gestión de comunidad, y después:
  python manage.py close_lost_schedule_activities --date 2026-05-31
  ```

- **Números esperados** (medidos contra el dump de producción del 2026-09-03): 1.173 actividades en
  1.167 pares; 1.124 pares van a status 4, 40 a status 5, 1 ya terminal, 2 sin estado de campaña.
  Sólo 57 pares pertenecen a campañas activas, así que el impacto sobre las colas vivas es chico.
- **Verificación post-deploy:** abrir `CampaignStatisticsDetailView` de una campaña activa antes y
  después y confirmar que `contacted_pct` no se movió — que es todo el punto del mapeo condicional.

## 🚀 Mejoras Futuras

- Reparar los 181 estados de campaña que el comando viejo pisó el 2025-07-01. Son identificables
  (`last_action_date='2025-07-01'` + `CW` + una suscripción atribuida a esa campaña), pero la
  resolución original no quedó registrada; lo más probable es `S2`, que es la que setean
  `handle_direct_sale` y `mark_as_sale`. Necesita ticket propio y decisión propia.
- Decidir qué hacer con `expire_old_pending_activities`: está etiquetado como `scheduled` en
  `COMMANDS.md` pero no está en ningún crontab, y no hay una sola fila en status `E`. O se agenda o se
  saca.
- Unas 700 agendas de junio a setiembre de 2026 ya están vencidas y quedan fuera de este corte por
  decisión explícita de gestión de comunidad — los vendedores todavía pueden trabajarlas. Si eso
  cambia, el mismo comando lo resuelve: es el mismo `--date`.

---

- **Fecha:** 2026-09-04
- **Autor:** Tanya Tree + Claude Opus 5
- **Branch:** t1175
- **Tipo de cambio:** Funcionalidad (+ Corrección)
- **Módulos afectados:** Core, Support
