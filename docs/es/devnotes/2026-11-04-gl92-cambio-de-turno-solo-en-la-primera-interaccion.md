# El cambio de turno por «No encontrado» sólo en la primera interacción

- **Fecha:** 2026-11-04
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl92-primera-interaccion-no-encontrado (it/utopia-crm-ladiaria#92)
- **Tipo:** Corrección
- **Componente:** Support (consola de ventas)
- **Impacto:** Experiencia de usuario

## 🎯 Resumen

Desde gl72 (it/utopia-crm-ladiaria#72), un «No encontrado» pasa al contacto al otro turno cuando es el primer «No
encontrado» de ese contacto en la campaña. El call center quería algo más estricto: el cambio de turno sólo tiene que
pasar cuando la **primera interacción** con el contacto en la campaña es un «No encontrado». Con la regla vieja, un
contacto agendado, o con un «Llamar más tarde» anterior, cambiaba de turno la primera vez que no contestaba, y no es
para eso el cambio de turno. Ahora cualquier actividad anterior del contacto en la campaña mantiene el comportamiento
de siempre.

## ✨ Cambios

### 1. Cualquier actividad anterior en la campaña es una interacción anterior

**Archivo:** `support/views/seller_console.py`

`get_first_not_found_switch_status()` buscaba sólo una llamada completada anterior cuya acción de consola fuera de tipo
`NOT_FOUND`. Ahora busca cualquier actividad del contacto en la campaña, de cualquier tipo, estado o vendedor:

```python
if Activity.objects.filter(contact=contact, campaign=campaign).exists():
    return None
return Shift.switch_status_at(moment)
```

Corre antes de que se registre la llamada actual, así que toda actividad que encuentra es anterior. En consecuencia:

- **Cola `act` (agendas, «Llamar más tarde»):** nunca cambia de turno, porque la actividad pendiente que se completa ya
  es una interacción anterior. El contacto se queda con su vendedor, recibe su actividad pendiente nueva y el offset
  avanza, como antes de gl72.
- **Cola `new`, sin actividades en la campaña:** cambia de turno como antes.
- **El otro turno:** no lo vuelve a cambiar, porque el primer «No encontrado» ya está registrado.
- **Las actividades de otras campañas** no cuentan.

Todo lo demás de gl72 sigue igual: la llamada se registra como «No encontrado», el aviso al vendedor, los botones de
turno según la hora y `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT`.

### 2. Tests

**Archivo:** `tests/test_seller_console.py`

- El test de la cola `act` se da vuelta: un contacto con una llamada agendada pendiente ya no cambia de turno, se queda
  con su vendedor y su actividad pendiente, y recibe el mensaje de éxito y el offset de siempre.
- Nuevo: un «No encontrado» después de un «Llamar más tarde» en la cola `new` se comporta como siempre.
- Nuevo: una actividad anterior de otro tipo y sin vendedor (un WhatsApp del call center) también cuenta.
- Nuevo: una actividad en otra campaña no cuenta, así que el contacto cambia de turno igual.

## 📁 Archivos Modificados

- **`support/views/seller_console.py`** — `get_first_not_found_switch_status()` busca cualquier actividad anterior en
  la campaña; docstring actualizado.
- **`tests/test_seller_console.py`** — Test de la cola `act` invertido y tres tests nuevos.
- **`local_settings_sample.py`** — El comentario de `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT` describe la regla
  nueva.
- **`CHANGELOG.md`** — Entrada.

## 🧪 Pruebas Manuales

1. **La primera interacción es «No encontrado» (caso feliz):**
   - Con dos turnos cargados, durante el de la mañana, abrir la consola de ventas en un contacto sin actividades en la
     campaña.
   - Apretar «No encontrado».
   - **Verificar:** el aviso amarillo dice que el contacto pasó al turno de la tarde, como en gl72.

2. **Contacto agendado:**
   - Agendar una llamada a un contacto de la campaña y, cuando venza, abrirlo desde la cola de actividades durante un
     turno.
   - Apretar «No encontrado».
   - **Verificar:** el mensaje verde de siempre; el contacto se queda con el vendedor, con una actividad pendiente
     nueva, y no pasa al otro turno.

3. **Primero «Llamar más tarde»:**
   - En un contacto sin actividades en la campaña, apretar «Llamar más tarde», volver a él y apretar «No encontrado».
   - **Verificar:** el mensaje verde de siempre y ningún cambio de turno.

## 📝 Notas de Despliegue

- No se requieren migraciones.
- No hay traducciones nuevas.
- Los contactos que ya se pasaron de turno con la regla vieja no vuelven.

## 🎓 Decisiones de Diseño

- **Cualquier actividad, no sólo las llamadas de la consola:** un WhatsApp del call center, un email o una venta
  directa registrados en la campaña también quieren decir que alguien ya atendió al contacto ahí.
- **Cuentan las pasadas anteriores por la misma campaña:** si un contacto sale de una campaña y lo vuelven a agregar,
  sus actividades viejas siguen apuntando a la campaña y mantienen el comportamiento de siempre. La regla es sobre el
  contacto en la campaña, no sobre su estadía actual.

---

- **Fecha:** 2026-11-04
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl92-primera-interaccion-no-encontrado
- **Tipo de cambio:** Corrección
- **Módulos afectados:** Support
