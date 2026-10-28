# No se crean incidencias de logística mientras hay un "No entregado" abierto

- **Fecha:** 2026-10-26
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl61-logistica-no-entregado-abierto
- **Tipo:** Mejora
- **Componente:** Support (formulario de nueva incidencia)
- **Impacto:** Lógica de negocio, interfaz

## 🎯 Resumen

Cuando una suscripción pasa a una ruta especial (`SPECIAL_ROUTES_FOR_SELLERS_LIST`), el base crea una incidencia de
servicio de la subcategoría `ISSUE_SUBCATEGORY_NOT_DELIVERED` (`logistics/utils.py`). Mientras esa incidencia está
abierta el diario no se entrega a propósito, así que una incidencia de logística como "no llegó" no tiene sentido,
pero nada impedía crearla. Con el setting nuevo `ISSUE_BLOCK_LOGISTICS_IF_NOT_DELIVERED_OPEN` prendido, la página de
nueva incidencia avisa de antemano y desactiva el botón de crear, y el formulario rechaza la incidencia si igual se
manda. Lo pidió el call center de la diaria (it/utopia-crm-ladiaria#61).

## ✨ Cambios

### 1. Setting `ISSUE_BLOCK_LOGISTICS_IF_NOT_DELIVERED_OPEN`

**Archivos:** `settings.py`, `local_settings_sample.py`

Por defecto es `False`: sin él, crear incidencias funciona exactamente igual que antes.

### 2. `get_blocking_not_delivered_issue(contact, category)`

**Archivo:** `support/forms.py`

Devuelve la incidencia de no entregado abierta que frena una incidencia nueva, o `None`. Sólo busca cuando el setting
está prendido y la categoría es logística (`L`). El control es por **contacto**, no por suscripción: frena cualquier
incidencia de servicio (`S`) abierta de la subcategoría `ISSUE_SUBCATEGORY_NOT_DELIVERED`. "Abierta" quiere decir que
su estado no está en `ISSUE_STATUS_FINISHED_LIST`, así que una incidencia sin estado cuenta como abierta, igual que en
`Contact.has_no_open_issues()`.

```python
contact.issue_set.filter(category="S", sub_category__slug=settings.ISSUE_SUBCATEGORY_NOT_DELIVERED)
    .exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
```

### 3. Aviso preventivo y botón de crear desactivado

**Archivos:** `support/views/all_views.py`, `support/templates/new_issue.html`

`NewIssueView` pone la incidencia que frena en el contexto como `blocking_issue`. El template muestra un
`alert-warning` arriba del formulario, con el link a esa incidencia, y el botón de crear sale `disabled`. El link
lleva `alert-link`: AdminLTE pinta de blanco los links comunes dentro de las alertas (`.alert a`), y sobre el
amarillo del aviso no se leen.

### 4. El `clean()` del formulario la rechaza

**Archivo:** `support/forms.py`

El botón desactivado es sólo una comodidad: sacándole el atributo desde el inspector del navegador se puede mandar
el formulario. `IssueStartForm.clean()` hace el mismo control y levanta un error sin campo, que muestra la alerta de
errores que el formulario ya tenía arriba. Como es un error de formulario común, la página se vuelve a mostrar con
todo lo que había cargado la persona.

El control usa el contacto del `initial` del formulario (que la vista arma desde la URL), no el campo oculto
`contact`: la vista guarda la incidencia para el contacto de la URL, así que editar el campo oculto no tiene que
saltearse el control.

## 📁 Archivos modificados

- **`settings.py`** — Setting nuevo, `False` por defecto.
- **`local_settings_sample.py`** — El setting, comentado, con su explicación.
- **`support/forms.py`** — `get_blocking_not_delivered_issue()` y el control en `IssueStartForm.clean()`.
- **`support/views/all_views.py`** — `blocking_issue` en el contexto de `NewIssueView`.
- **`support/templates/new_issue.html`** — Aviso y botón de crear desactivado.
- **`locale/es/LC_MESSAGES/django.po`** — El error y el aviso en español.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 📁 Archivos creados

- **`tests/test_new_issue_not_delivered_block.py`** — 9 tests: incidencias de no entregado abiertas, cerradas y sin
  estado; otras categorías; setting apagado; campo de contacto adulterado; el aviso y el botón desactivado en el GET;
  un POST frenado que no crea nada y conserva las notas cargadas; y el botón habilitado cuando nada frena.

## 🎓 Decisiones de diseño

- **En el base, no en un paquete de customización.** El base crea la incidencia de no entregado y es dueño del
  formulario de nueva incidencia, así que la regla es coherente acá. El setting la deja opcional para otras
  instalaciones.
- **Un error de formulario en vez de AJAX.** Validar al mandar ya conserva lo cargado y muestra el error donde el
  formulario muestra los demás; un control por AJAX sumaría código sin ganancia visible, porque el aviso ya aparece
  al cargar la página.
- **Por contacto, no por la suscripción elegida.** Un contacto con la entrega en espera no tiene que recibir
  incidencias de logística en ninguna de sus suscripciones.

## 🧪 Pruebas manuales

1. **Contacto con una incidencia de no entregado abierta (camino feliz):**
   - Prender el setting. Pasar una suscripción a una ruta especial para que se cree la incidencia de servicio, o
     crear a mano una incidencia de servicio con la subcategoría de no entregado.
   - Abrir "Nueva incidencia" para ese contacto.
   - **Verificar:** el aviso amarillo con el link a la incidencia, y el botón "Crear incidencia" desactivado.

2. **Saltearse el botón desactivado:**
   - En la misma página, sacarle `disabled` al botón con el inspector del navegador, completar el formulario y
     mandarlo.
   - **Verificar:** la alerta roja de error, el formulario conserva lo cargado y no se crea ninguna incidencia.

3. **Incidencia de no entregado cerrada:**
   - Cerrar la incidencia de no entregado y recargar la página.
   - **Verificar:** sin aviso, el botón habilitado y la incidencia de logística se crea.

4. **Setting apagado:**
   - Con el setting apagado y la incidencia de no entregado abierta, abrir la página.
   - **Verificar:** todo funciona como antes.

## 📝 Notas de despliegue

- No se requieren migraciones de base de datos.
- Compilar traducciones: `python manage.py compilemessages -l es`.
- Prender `ISSUE_BLOCK_LOGISTICS_IF_NOT_DELIVERED_OPEN = True` en el `local_settings.py` donde se quiera la regla, y
  revisar que `ISSUE_SUBCATEGORY_NOT_DELIVERED` coincida con el slug de la instalación.

---

- **Fecha:** 2026-10-26
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl61-logistica-no-entregado-abierto
- **Tipo:** Mejora
- **Módulos afectados:** Support
