# Vista General de Contacto: Compactación de UX y Optimizaciones de Consultas

**Fecha:** 2026-03-20
**Autor:** Trifero + programador AI en par
**Ticket:** t1060
**Tipo:** Mejora de UX, Rendimiento
**Componente:** Detalle de Contacto, Modelos Core
**Impacto:** Experiencia de Usuario, Rendimiento, Tiempo de Carga de Página

## 🎯 Resumen

Se refactorizaron las secciones de Últimas Incidencias y Últimas Actividades en la pestaña de vista general del detalle de contacto para que sean más compactas y legibles, reemplazando los ítems de tarjeta multi-línea por un diseño condensado de 2 líneas con notas expandibles. La cantidad de ítems mostrados también se aumentó de 3 a 5 para incidencias y actividades. Junto con los cambios visuales, se resolvieron varios problemas de consultas N+1: las actividades ahora usan `select_related` para vendedor y campaña, `get_subscriptionproducts()` ahora une dirección y ruta en una sola consulta, y `product_summary()` evita una consulta redundante a la base de datos cuando los productos de suscripción ya están precargados.

## ✨ Cambios

### 1. Lista Compacta de Incidencias en Vista General

**Archivo:** `support/templates/contact_detail/tabs/_overview.html`

La sección de últimas incidencias fue rediseñada de una tarjeta multi-párrafo por incidencia a un diseño ajustado de 2 líneas. La línea 1 muestra categoría–subcategoría, un badge de estado, la fecha de creación y un botón de vista, todo en una sola fila. La línea 2 muestra los primeros 60 caracteres de las notas, con un enlace "expandir" en línea cuando las notas superan esa longitud.

```html
<div class="list-group-item py-2 px-3">
  <div class="d-flex justify-content-between align-items-center">
    <span class="font-weight-bold">{{ issue.get_category }} – {{ issue.get_subcategory }}</span>
    <div class="d-flex align-items-center ml-2 flex-shrink-0">
      <span class="badge badge-secondary mr-2">{{ issue.get_status }}</span>
      <span class="text-muted mr-2">{{ issue.date_created|date:"d/m/Y" }}</span>
      <a href="..." class="btn btn-xs btn-outline-primary ..."><i class="fas fa-eye"></i></a>
    </div>
  </div>
  <!-- notas truncadas con enlace expandir -->
</div>
```

### 2. Lista Compacta de Actividades en Vista General

**Archivo:** `support/templates/contact_detail/tabs/_overview.html`

La sección de últimas actividades recibió el mismo tratamiento. La línea 1 muestra tipo de actividad, nombre de campaña opcional, badge de estado, fecha y vendedor. La línea 2 muestra notas truncadas (60 caracteres) con un enlace "expandir" que también revela la acción de consola del vendedor, tema, respuesta y campos de creado-por cuando están presentes.

### 3. JavaScript de Expandir/Contraer

**Archivo:** `support/templates/contact_detail/detail.html`

Se agregaron dos manejadores de click dentro del bloque `DOMContentLoaded` existente: uno para `.issue-notes-toggle` y otro para `.activity-extra-toggle`. Ambos alternan `d-none` en los spans corto/completo y cambian el texto del enlace entre "expandir" y "contraer".

```javascript
document.querySelectorAll(".issue-notes-toggle").forEach(link => {
  link.addEventListener("click", event => {
    event.preventDefault();
    const id = link.dataset.id;
    const shortEl = document.querySelector(`.issue-notes-short-${id}`);
    const fullEl = document.querySelector(`.issue-notes-full-${id}`);
    const expanded = fullEl.classList.toggle("d-none");
    shortEl.classList.toggle("d-none");
    link.textContent = expanded ? "expandir" : "contraer";
  });
});
```

### 4. Aumento de Ítems Mostrados y select_related para Actividades

**Archivo:** `support/views/contacts.py`

Los slices de `last_issues` y `activities` se aumentaron de 3 a 5 ítems. Tanto el slice de `activities` de la vista general como el queryset completo `all_activities` ahora usan `select_related("seller", "campaign")` para evitar una consulta a la base de datos por actividad cuando la plantilla accede a `a.seller.name` o `a.campaign.name`.

```python
activities = self.object.activity_set.all().select_related("seller", "campaign").order_by("-datetime", "id")[:5]
all_activities = self.object.activity_set.all().select_related("seller", "campaign").order_by("-datetime", "id")
last_issues = all_issues[:5]
```

### 5. Eliminación de N+1 en product_summary() mediante Caché de Prefetch

**Archivo:** `core/models.py` — `Subscription.product_summary()`

Cuando el `subscriptionproduct_set` de una suscripción ya está en `_prefetched_objects_cache` (como ocurre desde `ContactDetailView.prefetched_subscriptions`), el método ahora itera la lista en memoria en lugar de ejecutar una nueva consulta `SubscriptionProduct.objects.filter(subscription=self)`. El fallback a consulta de base de datos se preserva para todos los demás llamadores.

```python
if "subscriptionproduct_set" in getattr(self, "_prefetched_objects_cache", {}):
    subscription_products = self._prefetched_objects_cache["subscriptionproduct_set"]
    if with_pauses:
        subscription_products = [sp for sp in subscription_products if sp.active]
else:
    subscription_products = SubscriptionProduct.objects.filter(subscription=self)
    if with_pauses:
        subscription_products = subscription_products.filter(active=True)
```

### 6. Agregado address y route a select_related en get_subscriptionproducts()

**Archivo:** `core/models.py` — `Subscription.get_subscriptionproducts()`

La plantilla `_subscription_card.html` accede a `sp.address.address_1` y `sp.route.number` para cada producto de suscripción. Estos no estaban previamente incluidos en el join, causando una consulta extra por SP. Agregarlos a `select_related` resuelve el N+1 con un cambio mínimo.

```python
.select_related("product", "address", "route")
```

## 📁 Archivos Modificados

- **`support/templates/contact_detail/tabs/_overview.html`** — Rediseño de las secciones de últimas incidencias y últimas actividades con diseño compacto de 2 líneas y notas expandibles
- **`support/templates/contact_detail/detail.html`** — Agregados manejadores JavaScript de expandir/contraer para incidencias y actividades
- **`support/views/contacts.py`** — Agregado `select_related` para actividades; aumento del slice de incidencias y actividades a 5
- **`core/models.py`** — `product_summary()` usa caché de prefetch cuando está disponible; `get_subscriptionproducts()` une address y route

## 📚 Detalles Técnicos

- El enfoque de `_prefetched_objects_cache` en `product_summary()` utiliza la clave de caché interna estándar de Django para relaciones inversas precargadas. Es seguro leerla pero nunca debe escribirse directamente.
- Se intentó también pasar los productos precargados hacia `calc_price_from_products()` para omitir su llamada `Product.objects.in_bulk()`. Esto fue revertido porque `product_summary()` pasa su salida a través de `process_products()`, que puede reemplazar los IDs de producto originales con IDs de bundles generados por reglas de precio, haciendo que el conjunto de productos precargados sea incompleto para la búsqueda de precios.
- El `select_related("address", "route")` en `get_subscriptionproducts()` beneficia a todos los llamadores de este método en toda la base de código, no solo a la página de detalle de contacto.

## 🧪 Pruebas Manuales

1. **Visualización compacta de incidencias:**
   - Abrir la página de detalle de un contacto con al menos 2 incidencias que tengan notas con más de 60 caracteres.
   - **Verificar:** Cada incidencia se muestra como una fila compacta (categoría–subcategoría, badge, fecha, botón ojo). Una línea de notas truncadas aparece debajo con un enlace "expandir".
   - Hacer clic en "expandir".
   - **Verificar:** Las notas completas se muestran y el enlace cambia a "contraer". Hacer clic en "contraer" vuelve a la vista truncada.

2. **Visualización compacta de actividades:**
   - Abrir la página de detalle de un contacto con actividades que tengan campaña, vendedor y notas configurados.
   - **Verificar:** Cada actividad muestra tipo, nombre de campaña, badge de estado, fecha y vendedor en una fila. Las notas están truncadas con un enlace "expandir".
   - Hacer clic en "expandir".
   - **Verificar:** Se revelan las notas completas junto con la acción de consola del vendedor, tema, respuesta y campos de creado-por.

3. **Actividad sin contenido expandible:**
   - Encontrar una actividad sin notas, tema, respuesta, acción de consola del vendedor ni creado-por.
   - **Verificar:** Solo se muestra la fila de información; no aparece enlace expandir.

4. **Incidencia sin notas:**
   - Encontrar una incidencia sin notas.
   - **Verificar:** Solo se muestra la fila de información; no aparece línea de notas ni enlace expandir.

5. **Rendimiento — productos de suscripción:**
   - Abrir un contacto con múltiples suscripciones activas usando Django Debug Toolbar (o logging de consultas).
   - **Verificar:** No se ejecutan consultas `SELECT ... FROM core_subscriptionproduct WHERE subscription_id = ...` durante el renderizado de la página. No se ejecutan consultas `SELECT ... FROM core_address WHERE id = ...` por producto de suscripción.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- No hay comandos de gestión que ejecutar.
- El cambio en `get_subscriptionproducts()` aplica globalmente — verificar que cualquier plantilla o vista personalizada que llame a este método y dependa de que address o route se carguen de forma lazy siga funcionando correctamente (lo hará, ya que `select_related` solo agrega joins y nunca cambia la forma del queryset devuelto).

## 🚀 Mejoras Futuras

- Extender el patrón de caché de prefetch en `product_summary()` hacia `calc_price_from_products()` una vez que se identifique un enfoque seguro para manejar el remapeo de IDs de bundle en `process_products()`.
- Considerar aplicar el mismo patrón compacto de 2 líneas a la pestaña de actividades (`_activities.html`) para mantener consistencia en toda la página de detalle de contacto.

---

**Fecha:** 2026-03-20
**Autor:** Trifero + programador AI en par
**Branch:** t1060
**Tipo de cambio:** Mejora de UX, Rendimiento
**Módulos afectados:** Support, Modelos Core, Detalle de Contacto
