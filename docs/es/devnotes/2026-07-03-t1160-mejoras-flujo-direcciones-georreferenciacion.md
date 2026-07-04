# Renovación del Flujo de Direcciones: Campos Obligatorios, Edición en Un Paso y Resiliencia de Georref

- **Fecha:** 2026-07-03
- **Autor:** Tanya Tree + Claude Sonnet 5
- **Ticket:** t1160
- **Tipo:** Mejora
- **Componente:** Support (Direcciones), Modelos Core, Integración de Georreferenciación
- **Impacto:** Integridad de Datos, Experiencia de Usuario, Operabilidad

## 🎯 Resumen

Este ticket arrancó como un pedido simple — hacer obligatorios `address_1` y `address_2` en el formulario de direcciones, porque los operarios se olvidaban de cargarlos — y creció hasta convertirse en una limpieza más amplia de todo el ciclo de vida de las direcciones (agregar, editar, normalizar). En el camino aparecieron varios bugs reales de integridad de datos: direcciones que quedaban marcadas como `verified` después de editar su texto sin que las coordenadas cambiaran, un campo `georef_point` que "resucitaba" coordenadas viejas después de supuestamente limpiarlas, un crash sin manejar en la herramienta de normalización de direcciones, y un bug en la ficha de contacto que ocultaba justo el botón que más necesitaban los operarios (`Normalizar`) cuando la dirección lo necesitaba. Las llamadas HTTP al servicio de georreferenciación de Uruguay tampoco tenían timeout, así que un servicio lento o caído podía colgar un worker; ahora eso se maneja con timeout, manejo de errores, y un interruptor de apagado en base de datos que puede desactivar la georref al vuelo (a mano o automáticamente tras fallos repetidos) sin necesidad de un deploy.

## ✨ Cambios

### 1. Campos de dirección obligatorios

**Archivo:** `support/forms.py`

`SugerenciaGeorefForm` (usado tanto por `agregar_direccion` como por `editar_direccion`) ahora declara `address_1` y `address_2` como `required=True`, sobrescribiendo el `blank=True` del modelo. El modelo en sí no se tocó (otros flujos, como las importaciones CSV, siguen permitiendo `address_2` en blanco), así que no hace falta ninguna migración.

### 2. Elementos `<label>` reales con marcador de obligatoriedad

**Archivos:** `support/templates/location/agregar_direccion.html`, `support/templates/location/editar_direccion.html`

Los campos antes dependían solo del texto de `placeholder=` como etiqueta. Ahora tienen una etiqueta `<label>` propiamente dicha, con un asterisco rojo que se renderiza condicionalmente a partir de `form.<campo>.field.required` — siguiendo el mismo patrón que ya se usa en otras partes de la app (`bulk_delete_campaign_status.html`).

### 3. Endurecimiento del servicio de georreferenciación

**Archivo:** `util/location_utils.py`

Todas las llamadas HTTP a los servicios de georref de Uruguay ahora pasan por un único helper `_georef_get()` que agrega un `timeout` (`settings.GEOREF_TIMEOUT`, 5s por defecto) y captura `requests.exceptions.RequestException`, devolviendo `None` en vez de colgarse o levantar una excepción. Una nueva función `georef_habilitado()` reemplaza cada chequeo directo de `getattr(settings, "GEOREF_SERVICES", False)` en ambos repos (`support/location.py`, `support/views/{all_views,contacts,subscriptions}.py`, `utopia_crm_ladiaria/views/subscriptions.py`):

```python
def georef_habilitado():
    if not getattr(settings, "GEOREF_SERVICES", False):
        return False
    var, _ = Variable.objects.get_or_create(name="georef_services_enabled", defaults={"value": "1"})
    return var.value not in (None, "", "0")
```

El modelo `Variable` (ya usado en otras partes para configuración dinámica en base de datos) funciona como un interruptor de apagado dinámico por encima del setting estático `GEOREF_SERVICES` — editable desde el admin sin necesidad de un deploy. `_georef_get()` también trackea fallos consecutivos en una segunda `Variable` (`georef_fallos_consecutivos`); al llegar a `GEOREF_MAX_FALLOS_CONSECUTIVOS` (3 por defecto, `settings.py`) seguidos, apaga sola `georef_services_enabled` y loguea un error. Reactivarlo después de eso es manual (volver a poner la `Variable` en `"1"`) — sin reintento automático por tiempo, a propósito.

### 4. Checkbox de modo manual ("no pude encontrar la dirección")

**Archivos:** `support/templates/location/agregar_direccion.html`, `support/templates/location/editar_direccion.html`

Un checkbox aparece ahora arriba del buscador de direcciones. Al tildarlo:

- Oculta el buscador, la fila de latitud/longitud y el mapa; la columna del formulario pasa a ocupar todo el ancho.
- Vacía y deshabilita `latitude`, `longitude`, `city_georef_id`, `state_georef_id` para que no se puedan enviar con valores viejos.
- Desbloquea `address_1`/`city`/`state` para edición **sin** vaciar el texto actual — lo que ya estaba tipeado o sugerido se mantiene, así el operario solo corrige lo que está mal en vez de tener que reescribir todo.
- Revela un botón "Guardar sin georreferenciación" (`name="save_needs_georef"`).

### 5. `editar_direccion` pasa a ser un flujo de un solo paso

**Archivo:** `support/location.py`

`editar_direccion` antes forzaba un redirect a `normalizar_direccion` después de cualquier edición de texto. Ahora incorpora la misma interfaz de buscador + selección de sugerencia que `agregar_direccion`: elegir una sugerencia resuelve las coordenadas en el mismo request y muestra un botón "Guardar cambios", sin el salto forzado a una segunda pantalla. `normalizar_direccion` **no** se eliminó — sigue enlazada directamente desde las pestañas de la ficha de contacto y desde la herramienta de georref masivo, ambas necesitan usarla de forma independiente.

La fila de botones se reestructuró para calcar las ramas mutuamente excluyentes `if`/`elif` de `agregar_direccion` (estado resuelto → "Guardar cambios"; búsqueda fallida → botones de peligro; georref apagada → "Guardar cambios"), así el botón de guardado simple y los botones de "no encontrado" nunca se muestran al mismo tiempo.

### 6. Correcciones de integridad de datos

**Archivos:** `core/models.py`, `support/location.py`

Se encontraron y corrigieron varios bugs relacionados:

- **`Address.save()`** marcaba `verified = True` cuando los ids de departamento/ciudad y el punto geográfico estaban presentes, pero nunca bajaba `needs_georef` — una dirección podía quedar simultáneamente "verificada" y marcada "necesita georref", lo cual la interfaz de la ficha de contacto renderiza en rojo (un bug en sí mismo, ver punto 8). Se corrigió bajando también `needs_georef = False` en esa rama.
- **`Address.reset_georef()`** limpiaba `latitude`/`longitude`/`georef_point` pero no `state_georef_id`/`city_georef_id`. Ahora limpia los cuatro.
- **Resurrección de `georef_point` viejo:** `georef_point` no es un campo del formulario, así que vaciar `latitude`/`longitude` a través del checkbox de modo manual dejaba `georef_point` intacto en la instancia. `Address.save()` tiene lógica para *derivar* lat/long a partir de `georef_point` cuando faltan — lo cual resucitaba silenciosamente las coordenadas viejas al guardar. Las ramas `save_needs_georef` de `agregar_direccion` y `editar_direccion` ahora llaman a `reset_georef()` (que también limpia `georef_point`) en vez de poner `needs_georef = True` a mano y guardar.
- **Desacople texto/coordenadas:** `address_1`/`city`/`state` solo se bloqueaban como solo-lectura cuando una sugerencia se acababa de resolver *en ese mismo request* (`resolved_now`), no cuando la dirección ya tenía coordenadas válidas de antes. Eso significaba que abrir `editar_direccion` para una dirección ya verificada dejaba retipear `address_1` libremente mientras las coordenadas viejas, ahora desacopladas, seguían pegadas y `verified` se mantenía en `True`. Se corrigió bloqueando esos campos siempre que `lat and lng` estén presentes, y se simplificó aún más bloqueándolos siempre que `georef_activated` sea verdadero (sin importar si ya se eligió una sugerencia) — la única forma de escribir en ellos es a través del flujo de búsqueda o del checkbox de modo manual, así los operarios no pueden ponerse a escribir en campos que en definitiva no se van a guardar.

### 7. Correcciones en `normalizar_direccion`

**Archivos:** `support/location.py`, `support/templates/location/normalizar_direccion.html`

- `form_nuevo.address_1` era el único campo editable entre los datos de la sugerencia (ciudad/departamento/lat/long ya eran de solo lectura). Eso permitía que un operario cambiara el número de puerta después de elegir una sugerencia y guardara con las coordenadas *viejas* de la sugerencia todavía pegadas — `verified = True` con datos desacoplados. Ahora es de solo lectura, como el resto.
- Cuando la sugerencia elegida no tenía departamento resoluble (`seleccionar_sugerencia` devuelve su diccionario de fallo, con strings vacíos), la vista hacía slugify de un string vacío, no encontraba ningún `State` coincidente, y levantaba `StopIteration` — lo cual redirigía a `agregar_direccion` (flujo equivocado, crea una dirección nueva sin relación) con un mensaje confuso. Ahora se maneja con gracia: cae al departamento actual de la dirección, muestra el mensaje propio de "esta sugerencia no tiene datos de georreferenciación", y se queda en la página para que el operario pueda probar otra sugerencia del desplegable o usar el escape hatch existente de "Editar dirección".
- El `<select>` de sugerencias navega con `window.location = ...` al cambiar, lo cual disparaba el cartel de "¿Salir del sitio?" (`beforeunload`) de la página cada vez (el handler solo evita el aviso si se envió el *formulario*, no esta navegación interna). Se corrigió marcando `submitButtonPressed = true` antes de navegar.
- Ambas cards recibieron títulos más claros: la card izquierda es "Dirección actual (guardada)" (una referencia de solo lectura a lo que está guardado ahora mismo) con badge Normalizada/Sin normalizar; la card derecha es "Ubicación en el mapa" (si ya está verificada) o "Normalizar dirección" (si hay que elegir una sugerencia) — antes ambos estados mostraban el mismo encabezado engañoso "Dirección normalizada".

### 8. Pestaña de resumen de la ficha de contacto: botón Normalizar oculto

**Archivo:** `support/templates/contact_detail/tabs/_overview.html`

El listado de direcciones mostraba un ícono rojo ⊗ cuando `address.needs_georef`, y un link "Normalizar" solo en la rama `elif not address.verified` — mutuamente excluyentes por construcción. Como una dirección que necesita georref es (casi) siempre no verificada, el botón quedaba oculto justo cuando más se necesitaba. Se reestructuró para que el ícono y el link puedan coexistir: verificada → solo check verde; no verificada → ⊗ rojo (si `needs_georef`) *y* el link de Normalizar juntos.

## 📁 Archivos Modificados

- **`core/models.py`** — `Address.save()` baja `needs_georef` junto con `verified`; `Address.reset_georef()` también limpia `state_georef_id`/`city_georef_id`
- **`settings.py`** — Se agregaron `GEOREF_TIMEOUT` y `GEOREF_MAX_FALLOS_CONSECUTIVOS`
- **`support/forms.py`** — `address_1`/`address_2` obligatorios en `SugerenciaGeorefForm`
- **`support/location.py`** — `editar_direccion` reescrito como un flujo de búsqueda/resolución en un paso; `normalizar_direccion` ya no crashea con una sugerencia sin departamento; las ramas `save_needs_georef` usan `reset_georef()`
- **`support/templates/contact_detail/tabs/_overview.html`** — El link de Normalizar ya no queda oculto por `needs_georef`
- **`support/templates/location/agregar_direccion.html`** — etiquetas, asteriscos de obligatoriedad, checkbox de modo manual, fix de la card de mapa vacía, correcciones del bloqueo de solo-lectura
- **`support/templates/location/editar_direccion.html`** — igual que el anterior, más la interfaz de búsqueda embebida que reemplaza el viejo formulario de edición cruda
- **`support/templates/location/normalizar_direccion.html`** — `address_1` de solo lectura, fix del `beforeunload`, títulos de las cards
- **`support/views/all_views.py`**, **`support/views/contacts.py`**, **`support/views/subscriptions.py`** — usan `georef_habilitado()` en vez del chequeo directo del setting
- **`util/location_utils.py`** — wrapper `_georef_get()` (timeout, manejo de errores), `georef_habilitado()`, tracking de fallos consecutivos

## 🧪 Pruebas Manuales

1. **Agregar una dirección de punta a punta:**
   - Con `GEOREF_SERVICES = True`, ir a "Agregar dirección" de un contacto, tipear una calle en el buscador, elegir una sugerencia.
   - **Verificar:** `address_1`/`city`/`state` pasan a solo lectura con los valores resueltos, aparece un mapa, y "Guardar" persiste con `verified=True`, `needs_georef=False`.

2. **Editar una dirección ya verificada sin buscar:**
   - Abrir "Editar dirección" de una dirección que ya tiene coordenadas válidas. No tocar el buscador.
   - **Verificar:** `address_1`/`city`/`state` son de solo lectura desde el arranque (no hay forma de retipear la calle sin una búsqueda nueva o el modo manual), y se ve un único botón "Guardar cambios" — no ese botón junto con los de peligro.

3. **Caso borde — modo manual sobre una dirección previamente verificada:**
   - En esa misma dirección, tildar "cargar manualmente" y después "Guardar sin georreferenciación".
   - **Verificar:** `latitude`, `longitude`, `georef_point`, `state_georef_id`, `city_georef_id` quedan todos en `None`, `verified=False`, `needs_georef=True` — no sobrevive ninguna coordenada vieja.

4. **Caso borde — sugerencia sin departamento en `normalizar_direccion`:**
   - Navegar a `normalizar_direccion` para una dirección cuya primera sugerencia resuelve con departamento vacío (mockear el camino de fallo de `seleccionar_sugerencia`, o encontrar una así contra el servicio real).
   - **Verificar:** la página renderiza normalmente (200, no un redirect) mostrando el fallback de "sin datos de georref" y el desplegable de sugerencias, en vez de crashear con `StopIteration`.

5. **Caso borde — servicio de georref caído:**
   - Apuntar `SERVICIO_DIRECCION_AUTOCOMPLETADO` a un host inalcanzable, disparar 3 o más búsquedas consecutivas.
   - **Verificar:** cada llamada devuelve con gracia (sin colgarse, sin 500), y la `Variable` `georef_services_enabled` pasa a `"0"` después del tercer fallo; `georef_habilitado()` devuelve entonces `False` hasta que alguien la reactive.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- Las filas de `Variable` (`georef_services_enabled`, `georef_fallos_consecutivos`) se crean de forma perezosa en el primer uso vía `get_or_create` — no hace falta fixture ni migración de datos.
- `GEOREF_TIMEOUT` y `GEOREF_MAX_FALLOS_CONSECUTIVOS` tienen defaults razonables en `settings.py`; sobrescribir en `local_settings.py` solo si hace falta.
- Si en algún momento hay que apagar la georref rápido en producción sin un deploy, poner la `Variable` `georef_services_enabled` en `"0"` desde el admin de Django.

## 🚀 Mejoras Futuras

- Considerar una reactivación automática (basada en TTL) para el interruptor de georref en vez de requerir un reseteo manual, si las caídas repetidas se vuelven algo común.
- Los tres templates de direcciones (`agregar_direccion.html`, `editar_direccion.html`, y el JS compartido) ahora son casi duplicados; extraer un `{% include %}` compartido para el bloque de búsqueda/modo manual se postergó deliberadamente (ver la conversación del ticket) pero reduciría el riesgo de que se desincronicen.
- Las asperezas restantes de `normalizar_direccion.html` (mencionadas por la usuaria como "que también tiene cosas que arreglar") quedaron fuera del alcance de este ticket, más allá de los bugs puntuales listados arriba.

---

- **Fecha:** 2026-07-03
- **Autor:** Tanya Tree + Claude Sonnet 5
- **Branch:** t1160
- **Tipo de cambio:** Mejora
- **Módulos afectados:** Support (Direcciones), Modelos Core, Ficha de Contacto
