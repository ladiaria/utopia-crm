# La consola de ventas cambia de turno según la hora

- **Fecha:** 2026-10-29
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl72-cambio-de-turno (it/utopia-crm-ladiaria#72)
- **Tipo:** Mejora
- **Componente:** Support (consola de ventas, estadísticas de campañas)
- **Impacto:** Experiencia de usuario, Reportes

## 🎯 Resumen

El call center trabaja en dos turnos (`support.Shift`). Cuando nadie atiende la primera llamada a un contacto de una
campaña, el siguiente intento debería hacerlo el otro turno, pero el vendedor tenía que acordarse de apretar «Mover a
la tarde/mañana» a mano, y los dos botones se mostraban siempre. Ahora el primer «No encontrado» de un contacto en una
campaña lo pasa al otro turno según la hora, se le avisa al vendedor, y durante un turno sólo se ofrece pasar al otro.
La llamada se sigue registrando como «No encontrado», así que una customización puede contar las llamadas sin respuesta
(la diaria habilita un botón de WhatsApp después de tres: una en el primer turno y dos en el segundo). Los contactos que
se pasan de turno así ya no cuentan como contactados en las estadísticas, porque nadie atendió.

## ✨ Cambios

### 1. Turno del momento

**Archivo:** `support/models.py`

- `Shift.contains(moment)`: si la hora cae en el turno. Compara al minuto con el fin inclusivo, así que no queda hueco
  entre turnos, se cargue el fin como `14:59` o como `14:59:59`.
- `Shift.switch_status_at(moment)`: `SWITCH_TO_AFTERNOON` durante el turno de la mañana, `SWITCH_TO_MORNING` durante
  el de la tarde, `None` fuera de los dos. El turno de la mañana es el primero por hora de inicio y el de la tarde, el
  segundo, así que los nombres no importan. Si no hay exactamente dos turnos devuelve `None` y no cambia nada.

### 2. El primer «No encontrado» cambia de turno

**Archivo:** `support/views/seller_console.py`

`get_first_not_found_switch_status()` devuelve el estado al que pasar cuando la acción es de tipo `NOT_FOUND`, no hay
una llamada completada anterior de ese tipo para el contacto en la campaña (de ningún vendedor) y la hora cae en un
turno. Mira las actividades y no el estado de la campaña, porque al repartir los contactos del otro turno el estado
vuelve a «no contactado».

Cuando aplica:

- El `ContactCampaignStatus` toma ese estado y queda sin vendedor, como con los botones manuales; `last_console_action`
  queda en «No encontrado» y la resolución de campaña es la de la acción, como antes.
- La actividad se completa con la acción «No encontrado», como siempre.
- No se crea una actividad pendiente nueva (ni la de la cola `act` ni la de `KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY`):
  el contacto sale de las colas de este vendedor.
- El offset no se incrementa, porque el contacto sale de la lista y el siguiente ya queda en su lugar.
- El vendedor recibe un aviso (amarillo) en vez del mensaje de éxito de siempre, que dice que el contacto pasó al turno
  de la tarde o de la mañana.

`SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT = False` lo apaga; por defecto es `True`.

### 3. Sólo el pase al otro turno

**Archivos:** `support/views/seller_console.py`, `support/templates/seller_console.html`

El contexto tiene `show_move_morning` y `show_move_afternoon`: durante el turno de la mañana sólo se muestra «Mover a la
tarde», durante el de la tarde sólo «Mover a la mañana», y fuera de los turnos, los dos. El POST rechaza pasar al turno
actual. Esto no depende del setting.

### 4. No cuenta como contactado

**Archivos:** `core/choices.py`, `support/views/all_views.py`

`get_contacted_q()` es `status__in=get_contacted_statuses()` menos las filas en un estado de cambio de turno cuya última
acción de consola es un «No encontrado». Las seis estadísticas que contaban contactados (lista y detalle de campañas,
por vendedor y rendimiento de vendedores) lo usan. Las filas sin última acción de consola siguen contando.

## 📁 Archivos Modificados

- **`support/models.py`** — `Shift.contains()` y `Shift.switch_status_at()`.
- **`support/views/seller_console.py`** — Cambio de turno del primer «No encontrado», su aviso, el control del POST y
  los indicadores de los botones.
- **`support/templates/seller_console.html`** — Cada botón de turno se muestra según su indicador.
- **`core/choices.py`** — `get_contacted_q()`.
- **`support/views/all_views.py`** — Conteos de contactados con `get_contacted_q()`.
- **`local_settings_sample.py`** — `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT`.
- **`locale/es/LC_MESSAGES/django.po`** — Los tres textos nuevos.
- **`tests/test_seller_console.py`** — 13 tests nuevos: turno del momento (bordes, sin hueco, fuera de turno, sin dos
  turnos), primer «No encontrado» en cada turno, el segundo, fuera de los turnos, setting apagado, cola `act`, botones
  que se muestran, pase al turno actual rechazado y `get_contacted_q()`.
- **`CHANGELOG.md`** — Entrada.

## 🧪 Pruebas Manuales

1. **Primer «No encontrado» a la mañana (caso feliz):**
   - Cargar dos turnos en el admin (por ejemplo 09:00–14:59:59 y 15:00–21:00). Durante el de la mañana, abrir la consola
     de ventas en un contacto que nunca se llamó en la campaña.
   - Apretar «No encontrado».
   - **Verificar:** un aviso amarillo dice que el contacto pasó al turno de la tarde; la consola muestra el contacto
     siguiente (no el de después); el contacto aparece en «tarde» en la distribución de la campaña; su actividad tiene
     la acción «No encontrado».

2. **Segundo «No encontrado»:**
   - Asignar ese contacto a un vendedor del turno de la tarde y, durante la tarde, apretar «No encontrado».
   - **Verificar:** el mensaje verde de siempre; el contacto queda con el vendedor como «llamado, no se pudo contactar».

3. **Botones de turno:**
   - Abrir la consola durante la mañana, durante la tarde y fuera de los dos turnos.
   - **Verificar:** sólo «Mover a la tarde», sólo «Mover a la mañana» y los dos, respectivamente.

4. **Fuera de los turnos y setting apagado:**
   - Apretar «No encontrado» a las 22:00, y otra vez durante un turno con
     `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT = False`.
   - **Verificar:** los dos se comportan como antes de este cambio.

## 📝 Notas de Despliegue

- No se requieren migraciones.
- Recompilar traducciones: `python manage.py compilemessages -l es`.
- Verificar que haya exactamente dos turnos cargados (Support → Shifts). Sin ellos no cambia nada.
- El comportamiento viene prendido; para mantener el anterior, `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT = False`.

## 🎓 Decisiones de Diseño

- **Turnos por hora de inicio, no por nombre:** la app base no puede suponer los nombres de los turnos, y dos turnos
  ordenados por hora de inicio no son ambiguos.
- **«Primero» a partir de las actividades:** el estado de la campaña vuelve a 1 cuando el contacto se asigna al otro
  turno, así que no sirve para saber si hubo un «No encontrado» anterior.
- **La llamada sigue siendo un «No encontrado»:** el cambio de turno es una consecuencia de la llamada, no un resultado
  distinto, y los conteos de llamadas sin respuesta dependen de eso.

---

- **Fecha:** 2026-10-29
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl72-cambio-de-turno
- **Tipo de cambio:** Mejora
- **Módulos afectados:** Support, Core
