# Los teléfonos de otro país muestran de qué país son

- **Fecha:** 2026-10-20
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl19-pais-telefonos
- **Tipo:** Mejora
- **Componente:** Core (template tags), Support (ficha del contacto, consola del vendedor, incidencias)
- **Impacto:** Interfaz

## 🎯 Resumen

La ficha del contacto mostraba siempre `phone` y `mobile` en formato nacional (`as_national`), sin importar de qué
país fueran. Un celular local se ve bien, pero uno de otro país pierde el código: `+5491123456789` se mostraba como
`011 15-2345-6789`, y quien lo leía no tenía cómo saber que era argentino. Lo mismo pasaba con el botón de llamar por
SIP, que marcaba el formato nacional, así que llamaba a un número de otro país como si fuera local. Casi no entraban
números de otros países hasta que la compra del libro de la diaria empezó a aceptar celulares de cualquier país
(it/utopia-crm-ladiaria#15). Ahora los números de fuera de `PHONENUMBER_DEFAULT_REGION` se muestran en formato
internacional con la bandera de su país, y no tienen botón de llamar, porque el call center no marca al exterior.

## ✨ Cambios

### 1. Filtro `phone_display`

**Archivo:** `core/templatetags/core_tags.py`

Un filtro nuevo que mantiene el formato nacional para los números locales y muestra el resto en formato
internacional, seguido de la bandera:

```html
{{ contact.mobile|phone_display }}
<!-- +54 9 11 2345-6789 <span class="flag-icon flag-icon-ar" title="AR"></span> -->
```

El país local no está escrito a mano: sale de `PHONENUMBER_DEFAULT_REGION`. La decisión vive en una función común,
`foreign_region(value)`, que devuelve el código de región de un número válido de otro país y `None` para todo lo demás
(números locales, inválidos o vacíos, y cadenas de texto), para que el filtro de SIP pueda reutilizarla.

Las pestañas de la ficha del contacto (`_overview.html` y `_information.html`) usan el filtro para `phone` y `mobile`
en lugar de `as_national`.

### 2. Sin botón de llamar por SIP para los números de otro país

**Archivo:** `core/templatetags/sip_tags.py`

El filtro `sip` devuelve `phone_display` (número y bandera, sin botón) cuando `foreign_region` encuentra un país
extranjero. Eso cubre todas las plantillas que lo usan: la consola del vendedor, la consola de rutas especiales y la
vista de la incidencia. Los números locales, los inválidos y las cadenas de texto (`work_phone` es un `CharField`)
mantienen el botón como antes.

### 3. Banderas disponibles en todas las páginas

**Archivo:** `templates/adminlte/lib/_styles.html`

`flag-icon-css` ya venía con AdminLTE (`static/admin-lte/plugins/flag-icon-css/`) pero no se cargaba. Ahora se carga
con los estilos globales, porque las banderas aparecen en la ficha del contacto, en la consola del vendedor y en la
vista de la incidencia. La hoja de estilos sólo descarga el SVG de las banderas que efectivamente se muestran.

## 📁 Archivos Modificados

- **`core/templatetags/core_tags.py`** — Función `foreign_region` y filtro `phone_display`.
- **`core/templatetags/sip_tags.py`** — Filtro `sip` sin el botón para los números de otro país.
- **`support/templates/contact_detail/tabs/_overview.html`** — `phone` y `mobile` pasan por `phone_display`.
- **`support/templates/contact_detail/tabs/_information.html`** — Igual que la vista general.
- **`templates/adminlte/lib/_styles.html`** — Carga `flag-icon-css`.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 📁 Archivos Creados

- **`tests/test_phone_display.py`** — Tests de `phone_display` (números locales, de otro país, vacíos e inválidos) y
  del filtro `sip` (botón para números locales y cadenas de texto, sin botón para números de otro país).

## 🎓 Decisiones de Diseño

- **Formato internacional, no sólo la bandera.** Con la bandera al lado de `011 15-2345-6789`, el número se sigue
  leyendo como local y no se puede marcar tal como se muestra. El formato internacional lleva el código de país.
- **Bandera en lugar del nombre del país.** El proyecto instala `phonenumberslite`, que no trae los datos de
  geolocalización, así que el nombre del país no está disponible sin una dependencia nueva. La bandera viene de una
  librería que ya estaba incluida; al pasar el mouse se ve el código de región.
- **Los números inválidos mantienen su comportamiento.** Sin un número válido no hay un país confiable, así que se
  muestran en formato nacional y conservan el botón de llamar, como antes.
- **Sin botón de llamar para los números de otro país, en lugar de marcarlos en formato internacional.** El call
  center no marca al exterior.

## 🧪 Pruebas Manuales

1. **Contacto con celular de otro país (caso feliz):**
   - Abrir la ficha de un contacto cuyo celular sea de otro país (por ejemplo `+5521…`, Brasil) y cuyo teléfono sea
     local.
   - **Verificar:** en la vista general y en la pestaña Información, el teléfono se ve como antes y el celular aparece
     como `+55 21 …` seguido de la bandera de Brasil.

2. **Incidencia o consola del vendedor con un número de otro país:**
   - Abrir una incidencia (o la consola del vendedor) de un contacto con celular de otro país.
   - **Verificar:** el celular de otro país aparece con su bandera y sin el botón "Llamar"; un número local lo sigue
     teniendo.

3. **Número que el sistema no reconoce (caso borde):**
   - Abrir un contacto cuyo número se haya guardado sin un formato válido (por ejemplo, un número de otro país sin
     `+`).
   - **Verificar:** se muestra como antes, sin bandera, y conserva el botón de llamar.

4. **Tests automáticos:**

   ```bash
   python -W ignore manage.py test --settings=test_settings --keepdb tests.test_phone_display
   ```

   - **Verificar:** 7 tests OK.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No hay traducciones para compilar.
- No hay cambios de configuración: el país local es el `PHONENUMBER_DEFAULT_REGION` que ya existe.
- Correr `collectstatic` como en cualquier despliegue: `flag-icon-css` ya estaba en `static/`.

---

- **Fecha:** 2026-10-20
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl19-pais-telefonos
- **Tipo:** Mejora
- **Módulos afectados:** Core, Support
