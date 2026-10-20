# Punto de extensión para sumar acciones de venta en la consola del vendedor

- **Fecha:** 2026-10-20
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl45-whatsapp-callcenter
- **Tipo:** Mejora
- **Componente:** Support (consola del vendedor)
- **Impacto:** Extensibilidad

## 🎯 Resumen

La consola del vendedor no tenía ganchos: un paquete de customización que quisiera un botón propio junto a los
botones de resultado de la llamada tenía que sobreescribir el block `content` entero, copiando unas 500 líneas. Este
cambio agrega un block vacío en la columna "Acciones de Venta", para que un paquete sume acciones sobreescribiendo
sólo ese block. La motivación es el botón de WhatsApp del call center de la diaria (it/utopia-crm-ladiaria#45), que
es propio de ese despliegue y no corresponde al base.

## ✨ Cambios

### 1. El block `extra_sale_actions`

**Archivo:** `support/templates/seller_console.html`

`{% block extra_sale_actions %}` va en la columna de la derecha ("Acciones de Venta"), después de Vender / Enviar
promo (o de los botones de la suscripción, si el contacto ya tiene una) y antes de Programar. En el base está vacío,
así que la consola se ve exactamente igual que antes. Un paquete lo sobreescribe desde su propio
`seller_console.html`:

```html
{% extends "seller_console.html" %}

{% block extra_sale_actions %}
  <form method="post" action="{% url 'mi_accion' contact.id %}">
    {% csrf_token %}
    <button type="submit" class="btn btn-block bg-gradient-success btn-sm mt-1">Mi acción</button>
  </form>
{% endblock extra_sale_actions %}
```

El block ve el contexto de la consola: `contact`, `campaign`, `seller`, `console_instance`, `category`, `url` y
`offset`.

### 2. Los botones de resultado quedan fuera de `consoleForm`

HTML no permite formularios anidados, y una acción de un paquete que manda a otro lado necesita su propio formulario.
Por eso `consoleForm` ahora se cierra después de las notas y del motivo, y las tres columnas de botones van después:

- Los botones de resultado (`.result-btn`) nunca necesitaron estar adentro: son `type="button"` y mandan
  `consoleForm` por JavaScript, que lo busca por id.
- Los dos campos de Programar (`call_date`, `call_time`) se asocian a `consoleForm` con el atributo `form` de HTML, así
  que se siguen mandando con él.
- El resto de la columna son enlaces, que no dependen del formulario.

## 📁 Archivos modificados

- **`support/templates/seller_console.html`** — `consoleForm` se cierra antes de los botones; block vacío
  `extra_sale_actions`; `form="consoleForm"` en los campos de Programar. Las columnas de botones cambian un nivel de
  sangría, así que el diff se lee mejor ignorando espacios (`git diff -w`).
- **`CLAUDE.md`** — El gancho nuevo en *Extension patterns*.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 🎓 Decisiones de diseño

- **En la columna de acciones de venta, no debajo de toda la botonera.** Abajo de las tres columnas queda como un
  agregado, lejos de donde está mirando el vendedor. Junto a Vender / Enviar promo queda con las otras acciones que
  salen hacia la persona.
- **Sacar los botones del formulario en vez de documentar "acá no van formularios".** Un block adentro de
  `consoleForm` obligaría a que toda acción de un paquete fuera un enlace o mandara con `formaction`, y un botón submit
  adentro de `consoleForm` pasaría además a ser el destino del envío implícito (apretar Enter en el campo de fecha).
- **Un block, no uno por columna.** Hoy hay un solo uso real; se pueden agregar más cuando alguien los necesite.

## 🧪 Pruebas manuales

1. **Consola sin un paquete que use el block (camino feliz):**
   - Abrir la consola del vendedor de una campaña con contactos.
   - **Verificar:** los mismos botones que antes, en el mismo lugar.

2. **Programar sigue mandando fecha y hora:**
   - Elegir una fecha y una hora y apretar Programar.
   - **Verificar:** se crea la actividad agendada en esa fecha y hora.

3. **Los botones de resultado siguen funcionando:**
   - Elegir un motivo y apretar "No interesado"; en otro contacto, apretar "Llamar más tarde".
   - **Verificar:** los dos registran el resultado y pasan al siguiente contacto, como antes.

4. **Paquete que agrega una acción:**
   - Sobreescribir el block como en el ejemplo de arriba.
   - **Verificar:** el botón aparece debajo de Vender / Enviar promo, y al apretarlo manda su propio formulario, no
     `consoleForm`.

## 📝 Notas de despliegue

- No requiere migraciones.
- No hay traducciones para compilar.
- No hay cambios de configuración.

---

- **Fecha:** 2026-10-20
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl45-whatsapp-callcenter
- **Tipo:** Mejora
- **Módulos afectados:** Support
