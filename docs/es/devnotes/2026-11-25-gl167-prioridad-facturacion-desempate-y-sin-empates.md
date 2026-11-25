# Prioridad de facturación: desempate fijo y sin empates entre productos de facturación

- **Fecha:** 2026-11-25
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#167
- **Tipo:** Corrección de errores / Integridad de datos
- **Componente:** core (Product, Subscription)
- **Impacto:** Facturación, logística y quien edite productos en el admin

## 🎯 Resumen

La facturación toma la dirección, la ruta y el orden de reparto de cada factura de un producto de la suscripción: el que devuelve `Subscription.get_first_product_by_priority()`, el producto de tipo suscripción u otro con la `billing_priority` más baja. El nombre de la factura no sale de ahí: es el nombre de facturación de la suscripción o el del contacto.

La consulta ordenaba sólo por `billing_priority`. Cuando dos productos de una suscripción tenían el mismo número, la base de datos devolvía cualquiera de los dos, y nada garantizaba que devolviera el mismo la noche siguiente. Apareció en producción el 2026-11-24 con la suscripción 137634: Gigantes (prioridad 10, ruta 99) y Revista Crucigramas (prioridad 10, sin ruta). La revista ganó el empate, así que la suscripción quedaba sin ruta y no se facturaba desde el 2026-01-02. En producción empataban dos pares de productos activos (prioridades 1 y 10).

Dos cambios: las consultas ahora desempatan de forma fija, y el formulario del producto ya no deja que dos productos activos de facturación compartan prioridad.

## ✨ Cambios

### 1. Desempate fijo en todas las consultas por prioridad de facturación

**Archivo:** `core/models.py`

El nuevo `Product.billing_priority_order(prefix="")` devuelve el orden que usa la facturación: `billing_priority` con los NULL al final, y después el id del producto.

```python
return (F(f"{prefix}billing_priority").asc(nulls_last=True), f"{prefix}id")
```

Lo usan `get_first_product_by_priority()` y también `get_full_address_by_priority()`, `get_address_by_priority()` y `get_address_2_by_priority()`, que recorrían los productos por prioridad sin desempate.

- **Empates:** gana el producto de id más bajo, siempre el mismo.
- **NULL al final, explícito:** PostgreSQL ya ordena los NULL al final de menor a mayor, pero MySQL y MariaDB los ponen primero. Sin `nulls_last=True`, en esas bases un producto sin prioridad le ganaría a todos los que tienen número.

`get_first_product_by_priority()` sigue devolviendo `None` cuando la suscripción no tiene productos de tipo suscripción u otro. El nuevo `Product.BILLING_TYPES` nombra esos dos tipos.

### 2. Dos productos activos de facturación no pueden compartir prioridad

**Archivo:** `core/models.py`

`Product.clean_fields()` rechaza un producto activo de tipo suscripción u otro cuya `billing_priority` ya usa otro producto activo de esos tipos. El mensaje nombra al otro producto y su id. Se permiten la prioridad vacía, los productos inactivos, las newsletters y los descuentos.

- **Sólo cuando cambia:** la validación corre para un producto nuevo, o cuando su prioridad, su tipo o su activo difieren de los guardados (`billing_priority_changed()`). Así, los empates guardados antes de esta regla no traban editar los demás campos de esos productos. Igual hay que corregirlos a mano.
- **Formularios sin el campo:** la lista de productos del admin edita algunas columnas en el lugar, pero no la prioridad. Cambiar ahí el tipo de un producto todavía puede crear un empate. Un error de campo para un campo que el formulario no tiene lanzaría `ValueError`, así que en ese caso el error no va a ningún campo. Es el patrón que da la documentación de Django para `clean_fields()`.

`billing_priority_tie()` devuelve el otro producto, o `None`. Un paquete de customización puede usarlo, junto con `BILLING_TYPES`, para listar los empates.

### 3. Traducción al español

**Archivo:** `locale/es/LC_MESSAGES/django.po`

El mensaje nuevo se agregó a mano. `makemessages` habría reescrito el archivo entero, con las referencias de línea corridas y otros strings sin traducir.

## 📁 Archivos modificados

- **`core/models.py`** — `Product.BILLING_TYPES`, `billing_priority_order()`, `billing_priority_tie()`, `billing_priority_changed()`, `clean_fields()`; los cuatro métodos `*_by_priority` de `Subscription` usan el orden nuevo
- **`locale/es/LC_MESSAGES/django.po`** — Traducción del mensaje de validación
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos creados

- **`tests/test_product_billing_priority.py`** — Desempate por id, NULL al final, sólo cuentan los productos de suscripción y otro, las direcciones usan el mismo orden, y la validación (nuevo, cambiado, activado, casos permitidos, empate guardado, formulario sin el campo)

## 🧪 Pruebas manuales

1. **Empate rechazado:** en el admin, abrir un producto activo de suscripción y ponerle la prioridad de otro producto activo de suscripción. **Verificar:** el formulario vuelve con un error bajo «Prioridad de facturación» que nombra al otro producto y su id.
2. **Prioridad vacía permitida:** vaciar la prioridad y guardar. **Verificar:** se guarda.
3. **Caso borde, empate guardado:** con dos productos activos que ya comparten prioridad (como en producción antes de corregirlos), cambiar el precio de uno. **Verificar:** se guarda, sin error.
4. **Caso borde, lista del admin:** en la lista de productos, cambiar a «Suscripción» el tipo de una newsletter que tiene la prioridad de un producto activo de suscripción, y guardar. **Verificar:** la fila vuelve con el error, y la página no se rompe.
5. **Facturación:** en una suscripción con dos productos que comparten prioridad, `subscription.get_first_product_by_priority()` devuelve siempre el de id más bajo.

## 📝 Notas de despliegue

- No se requieren migraciones ni settings.
- **Los empates de producción quedan hasta que alguien los corrija:** `la-diaria-lunes` y `modragon-full` en 1, `gigantes` y `revista-crucigramas` en 10 (2026-11-24). Después del deploy, la facturación elige el id más bajo de cada par: `la-diaria-lunes` y `gigantes`.
- Mergear esto antes que el lado de `utopia-crm-ladiaria` del mismo issue (una vista de las prioridades). Esa vista no importa nada nuevo de acá, pero dice que los empates los gana el id más bajo, y eso recién es cierto después de este deploy.

## 🎓 Decisiones de diseño

- **Por qué validar sólo cuando cambia:** validar en cada guardado habría trabado editar cualquier campo de los cuatro productos empatados hasta corregirlos, y uno de ellos espera una decisión de negocio. La regla sólo tiene que frenar los empates nuevos.
- **Por qué `clean_fields()` y no `clean()`:** `clean()` no recibe `exclude`, así que no puede saber cuándo el formulario no tiene el campo de prioridad. `clean_fields()` sí, y convierte el error en uno que no va a ningún campo.
- **La validación corre sólo en formularios:** como cualquier validación de modelo en Django, `Product.objects.create()` y `save()` no la llaman. Los productos se editan en el admin, así que alcanza.
- **No se validan los productos inactivos**, como pide el issue. `get_first_product_by_priority()` no filtra por activo, así que un producto inactivo que siga en suscripciones igual competiría. El 2026-11-25 ningún producto inactivo empataba con uno activo.

---

- **Fecha:** 2026-11-25
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl167-prioridad-facturacion
- **Tipo:** Corrección de errores / Integridad de datos
- **Módulos afectados:** core
