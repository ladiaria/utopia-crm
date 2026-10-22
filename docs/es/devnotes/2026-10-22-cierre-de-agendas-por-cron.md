# Cierre de agendas perdidas desde un cron diario

- **Fecha:** 2026-10-22
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl58-cierre-agendas-cron (it/utopia-crm-ladiaria#58)
- **Tipo:** Mejora
- **Componente:** Core (campañas), Logistics
- **Impacto:** Operación, ruido de los mails del cron

## 🎯 Resumen

`close_lost_schedule_activities` (t1175) se hizo para cortes puntuales: sólo aceptaba una fecha fija con `--date`. La
diaria ahora lo quiere como rutina diaria ("cerrar toda agenda con más de 30 días de vencida", 15 días desde el
2026-11-30), así que el comando suma un plazo relativo, `--days N`. Cron manda por mail todo lo que imprime un
comando, y el resumen diario llegaría a una casilla todas las noches, así que este comando y `create_deliveries`
ahora respetan `--verbosity 0`: una corrida normal no imprime nada y el mail llega sólo cuando algo falla. La nota que
queda en cada actividad cerrada ya no lleva el número de ticket `t1175`, que no tenía sentido en una rutina que corre
todos los días.

## ✨ Cambios

### 1. `--days N`, excluyente con `--date`

**Archivo:** `core/management/commands/close_lost_schedule_activities.py`

Las dos opciones van en un grupo excluyente obligatorio, así que el comando sigue sin tener un corte por defecto:
nadie tiene que cerrar agendas por accidente. `--days N` equivale a `--date` con la fecha de hace N días, y pasa por
el mismo `get_cutoff`, así que el día del corte entra entero. Un `--days` negativo aborta con un `CommandError`.

```bash
python manage.py close_lost_schedule_activities --days 30 --verbosity 0
```

### 2. Corridas en silencio con `--verbosity 0`

**Archivos:** `core/management/commands/close_lost_schedule_activities.py`,
`logistics/management/commands/create_deliveries.py`

- `close_lost_schedule_activities` condiciona cada línea informativa a `verbosity >= 1`: el resumen, el aviso de "no
  es un dry run", el mensaje del CSV, "no hay agendas para cerrar" y el conteo final. La única excepción es la lista
  de agendas **sin** `ContactCampaignStatus`: son una anomalía, así que se imprimen con cualquier verbosidad y el mail
  del cron las trae.
- `create_deliveries` usaba `print()` a secas, que ignora `--verbosity`. Ahora escribe con `self.stdout.write` y con
  verbosidad 0 no imprime nada.

Los errores no cambian: una excepción sigue terminando en un traceback por stderr, que cron manda por mail.

### 3. La nota de la actividad sin el número de ticket

**Archivos:** `core/management/commands/close_lost_schedule_activities.py`, `locale/es/LC_MESSAGES/django.po`

La nota pasó de *"Cerrado automáticamente por agenda perdida (t1175, AAAA-MM-DD)."* a *"Cerrado automáticamente por
agenda perdida (AAAA-MM-DD)."*. Cambia el msgid, y su traducción con él. Las notas ya escritas conservan el texto
viejo.

## 📁 Archivos Modificados

- **`core/management/commands/close_lost_schedule_activities.py`** — `--days`, salida condicionada a la verbosidad,
  nota sin el número de ticket.
- **`logistics/management/commands/create_deliveries.py`** — `self.stdout.write` en lugar de `print()`, en silencio
  con verbosidad 0.
- **`locale/es/LC_MESSAGES/django.po`** — msgid nuevo para la nota.
- **`tests/test_close_lost_schedule.py`** — El test de la nota verifica la fecha en vez de `t1175`; nuevo
  `CloseLostScheduleCronTest` (7 tests: corte de `--days` inclusive, opciones excluyentes, corte faltante, días
  negativos, corrida en silencio, corrida en silencio sin nada para cerrar, la anomalía se sigue informando).
- **`COMMANDS.md`** — `close_lost_schedule_activities` pasa a `scheduled`; las dos filas mencionan `--verbosity 0`.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 📁 Archivos Creados

- **`tests/test_create_deliveries.py`** — En silencio con verbosidad 0, y por defecto sigue informando el proceso.

## 🧪 Pruebas Manuales

1. **Corte diario (camino feliz):**
   - Correr `python manage.py close_lost_schedule_activities --days 30 --dry-run`.
   - **Verificar:** el resumen cuenta las agendas con fecha de hace 30 días o más, y no se escribe nada.

2. **Corrida de cron en silencio:**
   - Correr `python manage.py close_lost_schedule_activities --days 30 --verbosity 0`.
   - **Verificar:** no hay salida; las agendas quedan cerradas y su nota dice "Cerrado automáticamente por agenda
     perdida (fecha)." sin número de ticket.

3. **Corte faltante o contradictorio (caso borde):**
   - Correr el comando sin corte, después con `--days 30 --date 2026-05-31`, y después con `--days -1`.
   - **Verificar:** las tres corridas abortan sin tocar nada.

4. **`create_deliveries` en silencio:**
   - Correr `python manage.py create_deliveries --verbosity 0`.
   - **Verificar:** no hay salida, y los repartos del día se crean igual que antes.

## 📝 Notas de Despliegue

- No se requieren migraciones.
- **Recompilar traducciones** (`python manage.py compilemessages -l es`): cambió el msgid de la nota. Sin eso la nota
  se escribe en inglés.
- Las líneas del cron pueden pasar de `--date $(date -d '30 days ago' +\%F)` a `--days 30`, y sumar `--verbosity 0` a
  los dos comandos. Agregar `--verbosity 0` antes de este deploy no hace daño: el código viejo lo ignora.

## 🎓 Decisiones de Diseño

- **`--days` como atajo de `--date`, no un segundo camino.** Los dos terminan en el mismo `get_cutoff`, así que un
  cron con `--days 30` y una corrida manual con la fecha equivalente cierran exactamente las mismas agendas.
- **Las anomalías sobreviven a `--verbosity 0`.** La idea del modo silencioso es que un mail signifique "mirá esto".
  Una agenda sin estado de campaña es justamente eso, así que es lo único que se sigue imprimiendo.

---

- **Fecha:** 2026-10-22
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl58-cierre-agendas-cron
- **Tipo de cambio:** Mejora
- **Módulos afectados:** Core, Logistics
