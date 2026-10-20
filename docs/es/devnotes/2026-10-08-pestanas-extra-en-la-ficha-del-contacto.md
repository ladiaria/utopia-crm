# Puntos de extensión para pestañas extra en la ficha del contacto

- **Fecha:** 2026-10-08
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl21-contact-detail-extra-tabs
- **Tipo:** Mejora
- **Componente:** Support (ficha del contacto)
- **Impacto:** Extensibilidad

## 🎯 Resumen

La lista de pestañas de la ficha del contacto está escrita a mano en la plantilla del base, y su único gancho era el
block `whatsapp_messages_count`, que vive adentro del enlace de la pestaña de WhatsApp. Un paquete de customización
que quisiera una pestaña propia tenía que sobrescribir el block `content` entero, copiando unas 125 líneas de una
plantilla que cambia seguido. Este cambio agrega dos blocks vacíos, uno para pestañas extra y otro para sus paneles,
para que un paquete pueda sumar pestañas sobrescribiendo sólo esos blocks. La motivación es la pestaña de WhatsApp
de la radio de la diaria, que es propia de esa instalación y no corresponde al base.

## ✨ Cambios

### 1. Blocks `extra_tabs` y `extra_tab_panes`

**Archivo:** `support/templates/contact_detail/detail.html`

- `{% block extra_tabs %}` va en la barra de pestañas (`#contact-detail-tabs`), justo después de la pestaña de
  WhatsApp y antes de la de Facturas, que sigue siendo la última porque tiene estilo de botón.
- `{% block extra_tab_panes %}` va al final de `.tab-content`, después del panel de Facturas.

Los dos están vacíos en el base, así que la página se ve exactamente igual que antes. Un paquete los sobrescribe
desde su propio `contact_detail/detail.html`, que ya extiende al del base:

```html
{% extends "contact_detail/detail.html" %}

{% block extra_tabs %}
  <li class="nav-item">
    <a class="nav-link" href="#my_tab" data-toggle="tab">My tab
      <div class="ml-1 badge badge-pill badge-primary">{{ count }}</div>
    </a>
  </li>
{% endblock extra_tabs %}

{% block extra_tab_panes %}
  <div class="tab-pane" id="my_tab">{% include "contact_detail/tabs/_my_tab.html" %}</div>
{% endblock extra_tab_panes %}
```

El `href` de cada pestaña tiene que coincidir con el `id` de su panel, igual que en las pestañas del base.

## 📁 Archivos Modificados

- **`support/templates/contact_detail/detail.html`** — Dos blocks vacíos, `extra_tabs` y `extra_tab_panes`.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 🎓 Decisiones de Diseño

- **Blocks vacíos en lugar de una pestaña de relleno.** La pestaña de WhatsApp sigue otro patrón: el base muestra una
  pestaña con el texto "This is not configured" y el paquete sobrescribe la plantilla incluida. Eso obliga a toda
  instalación a mostrar una pestaña que quizás no usa. Los blocks vacíos no agregan nada salvo que un paquete los
  llene.
- **Antes de Facturas, no al final de todo.** Facturas tiene estilo de botón rojo o verde y funciona como cierre de
  la barra; las pestañas agregadas después quedarían fuera de lugar.
- **Dos blocks y no uno.** La pestaña y su panel viven en partes distintas del marcado (`.card-header` y
  `.card-body`), así que un solo block no puede contener a los dos.

## 🧪 Pruebas Manuales

1. **Ficha sin ningún paquete que use los blocks (camino feliz):**
   - Abrir la ficha de cualquier contacto.
   - **Verificar:** las mismas pestañas que antes, en el mismo orden, y cada una abre su panel.

2. **Paquete que agrega una pestaña:**
   - En una plantilla de un paquete que extienda `contact_detail/detail.html`, sobrescribir los dos blocks como en
     el ejemplo de arriba.
   - Abrir la ficha de un contacto.
   - **Verificar:** la pestaña nueva aparece entre "Mensajes de WhatsApp" y "Facturas", y al hacer clic muestra su
     panel.

3. **Paquete que sobrescribe la plantilla pero no estos blocks (caso borde):**
   - Con un paquete cuyo `contact_detail/detail.html` extiende al del base y sólo llena otros blocks (como hace hoy
     `utopia_crm_ladiaria`), abrir la ficha de un contacto.
   - **Verificar:** la página es idéntica a la de antes de este cambio: la misma cantidad de pestañas y paneles.

## 📝 Notas de Despliegue

- No se requieren migraciones.
- No hay traducciones para compilar.
- No hay cambios de configuración.

---

- **Fecha:** 2026-10-08
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl21-contact-detail-extra-tabs
- **Tipo de cambio:** Mejora
- **Módulos afectados:** Support
