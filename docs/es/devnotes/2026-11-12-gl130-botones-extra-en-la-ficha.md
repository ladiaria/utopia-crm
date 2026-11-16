# La barra de botones de la ficha del contacto suma un bloque de extensión

- **Fecha:** 2026-11-12
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#130
- **Tipo:** Mejora
- **Componente:** Support (ficha del contacto)
- **Impacto:** Extensibilidad

## 🎯 Resumen

El paquete de customización necesitaba un botón en la ficha del contacto: «Vender producto de una única vez», para los vendedores (it/utopia-crm-ladiaria#130). La barra de botones de arriba de las pestañas (Nueva actividad, Nueva incidencia…) no tenía punto de extensión, así que la única forma de agregar un botón era copiar el bloque `content` entero. Un bloque nuevo y vacío, `extra_actions`, queda al final de esa barra. Es la misma idea que `extra_sale_actions` en la consola de venta.

## ✨ Cambios

### 1. `extra_actions` en la ficha del contacto

**Archivo:** `support/templates/contact_detail/detail.html`

```django
      {% block extra_actions %}{% endblock extra_actions %}
    </div>
  </section>
```

Un bloque vacío dentro de la barra de botones, después de los botones que ven sólo Support y Managers. Queda **fuera** de ese chequeo de grupo: cada botón que agrega un paquete chequea su propio permiso. Lo llena el `contact_detail/detail.html` de un paquete, que extiende el del base.

### 2. Documentado con los demás puntos de extensión

**Archivo:** `CLAUDE.md`

«Extra contact detail actions» se suma a la lista de patrones de extensión, junto a las pestañas extra y las secciones extra de la tarjeta de suscripción.

## 📁 Archivos modificados

- **`support/templates/contact_detail/detail.html`** — El bloque `extra_actions`
- **`CLAUDE.md`** — El punto de extensión nuevo
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas manuales

Acá no hay tests automáticos: el bloque está vacío. Lo llena el paquete de customización, y sus tests verifican que el botón aparece para un usuario que puede vender y no para uno que no (`utopia_crm_ladiaria/tests/test_venta_oneshot.py`).

1. **Caso normal, con un paquete que llena el bloque:**
   - En la diaria, entrá como vendedor y abrí un contacto.
   - **Verificar:** «Vender producto de una única vez» aparece al final de la barra de botones.

2. **Caso borde, sin paquete:**
   - Abrí un contacto sin ningún paquete que extienda `contact_detail/detail.html`.
   - **Verificar:** La barra de botones se ve igual que antes.

## 📝 Notas de deployment

- Sin migraciones ni settings.
- **Orden con el paquete:** cualquiera de los dos puede ir primero. Sin este bloque no se rompe nada, pero el botón del paquete no aparece en la ficha hasta que esto se deploye.

## 🎓 Decisiones de diseño

- **Fuera del chequeo de Support y Managers:** los botones que ya están ahí son para esos grupos; el de un paquete puede ser para otros usuarios (los vendedores), así que decide él quién lo ve.
- **Al final de la barra:** los botones del base no se mueven de lugar.

---

- **Fecha:** 2026-11-12
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl130-ficha-extra-actions
- **Tipo:** Mejora
- **Módulos afectados:** support
