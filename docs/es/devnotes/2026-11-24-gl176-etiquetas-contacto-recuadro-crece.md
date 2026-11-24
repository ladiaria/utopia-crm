# Etiquetas del contacto: el recuadro de Tagify crece, así la ✕ de cualquier etiqueta la borra

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#176
- **Tipo:** Corrección de errores
- **Componente:** support (formulario de edición de contacto, filtro de la lista de contactos)
- **Impacto:** Quien edite las etiquetas de un contacto

## 🎯 Resumen

El campo Etiquetas del formulario de edición de contacto es un recuadro de Tagify. El template renderiza el input con `class="form-control"`, y Tagify copia las clases del input a su recuadro (`<tags class="tagify … form-control">`). Bootstrap le da a `.form-control` una altura fija de una línea, así que el recuadro mostraba una fila de etiquetas con scroll: 32 px para 327 px de contenido, en un contacto de prueba con 41 etiquetas. Hacer click en la ✕ de una etiqueta fuera de la última fila no hacía nada visible salvo bajar el scroll hasta el final. Al apretar el botón, Tagify le da el foco a su campo de texto, que está después de la última etiqueta, así que el navegador bajaba el scroll hasta él y el click caía en otro lado. Para sacarle `eliminar` al contacto 705442 en producción hubo que borrar con el teclado todas las etiquetas que estaban después. Ahora el recuadro crece con sus etiquetas.

## ✨ Cambios

### 1. El recuadro de Tagify crece con sus etiquetas

**Archivos:** `support/templates/create_contact/create_contact.html`, `support/templates/contact_list.html`

El `<style>` de la página saca `max-height: 150px`, `overflow-y: auto` y el padding para la barra de scroll, y agrega:

```css
.tagify.form-control {
  height: auto;
}
```

El borde y el degradado del fondo se mantienen. El filtro de la lista de contactos tenía el mismo estilo y el mismo `form-control`, así que lleva el mismo arreglo. Sin etiquetas, mide lo mismo que los otros filtros.

### 2. Se va el texto de ayuda del scroll

**Archivos:** `support/templates/create_contact/tabs/_data.html`, `locale/es/LC_MESSAGES/django.po`

Se saca «Desliza para ver todas las etiquetas» del formulario, y su entrada del `.po`.

## 📁 Archivos modificados

- **`support/templates/create_contact/create_contact.html`** — Estilo del recuadro de Tagify
- **`support/templates/contact_list.html`** — El mismo estilo para el filtro de etiquetas
- **`support/templates/create_contact/tabs/_data.html`** — Se saca el texto de ayuda del scroll
- **`locale/es/LC_MESSAGES/django.po`** — Entrada del texto sacado
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas manuales

1. **Caso normal:** abrir «Editar contacto» de un contacto con unas 40 etiquetas. **Verificar:** se ven todas, sin scroll dentro del campo. Hacer click en la ✕ de una etiqueta de la primera fila. **Verificar:** desaparece en el momento. Guardar. **Verificar:** el contacto ya no la tiene.
2. **Caso borde, pocas etiquetas:** un contacto con una etiqueta y uno sin ninguna. **Verificar:** el campo mide lo mismo que los otros.
3. **Caso borde, lista de contactos:** abrir la lista de contactos. **Verificar:** el filtro Etiquetas se ve como los otros filtros; agregar y sacar un par de etiquetas.

Hecho en local el 2026-11-24: antes del arreglo el recuadro medía 32 px para 327 px de contenido, y la ✕ de una etiqueta de la primera fila sólo movía el `scrollTop` de 0 a 295. Después mide 327 px y la ✕ borra la etiqueta al primer click, y al guardar queda borrada.

## 📝 Notas de despliegue

- Sin migraciones ni settings.
- No hace falta `compilemessages`: sólo se sacó una entrada que ya no se usa.

## 🎓 Decisiones de diseño

- **Sin tope de altura.** Un contacto con 40 etiquetas hace que el campo tenga unas diez filas, y eso es mejor que cualquier scroll: con scroll, el problema del click vuelve apenas el contenido supera el tope.
- **CSS, no otro widget.** Un buscador dentro del campo o select2 podrían hacer más cómodas las listas grandes, pero el problema reportado era sacar etiquetas, y esto lo resuelve sin cambiar cómo funciona el campo.

---

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl176-etiquetas-contacto
- **Tipo:** Corrección de errores
- **Módulos afectados:** support
