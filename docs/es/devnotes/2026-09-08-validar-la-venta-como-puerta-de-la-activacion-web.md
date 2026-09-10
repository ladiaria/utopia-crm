# Validar la venta como puerta de la activación en la web

- **Fecha:** 2026-09-08
- **Autor:** Tanya Tree + Claude Opus 5
- **Ticket:** rama `desync/validacion-y-activacion` (frente desync CRM ↔ CMS, tarea 3)
- **Tipo:** Nueva funcionalidad (+ correcciones en suscripciones gratuitas y en el detalle del contacto)
- **Componente:** Core — Suscripciones, Utils; Support — Registros de venta, vistas de validación, sidebar
- **Impacto:** Propagación del acceso web, comisiones, integridad de datos, experiencia de usuario

## 🎯 Resumen

Una suscripción creada por el call center no existía para el sitio hasta que corría el batch nocturno
de `activos.csv`: la persona pagaba a la mañana y seguía chocando con el paywall hasta el día
siguiente. El CRM ya sabe pedirle al CMS que active a un suscriptor
(`utopia_crm_ladiaria/services/activation.py`, en producción desde el 2026-08-12, lo usa Witty), así
que lo que faltaba era **cuándo** llamarlo desde una venta de call center.

La respuesta que implementa esta rama es **en la validación, no en el alta**. Una venta recién hecha
todavía puede ser un duplicado —la misma persona con dos cuentas web, que es justo lo que la cola de
desduplicación resuelve a mano—, y dar el acceso antes de que un humano la haya mirado se lo da, la
mitad de las veces, a la cuenta equivocada. La validación es el momento en que alguien ya miró.

Colgar el acceso web de la validación sólo sirve si la cola de validación significa algo, y no
significaba nada: **toda** suscripción nacía sin validar, incluidas las que entran por la web, que no
tienen vendedor, ni comisión, ni nada que un manager pueda validar. La cola era una pila que nadie
leía. Por eso la rama además ordena quién lleva registro de venta y quién nace validada, corrige qué
reportan las gratuitas y hace visible el estado de validación desde la ficha del contacto para todos
los tipos de suscripción.

## ✨ Cambios

### 1. Un gancho para lo que "validado" tiene que disparar

**Archivos:** `core/utils.py`, `support/views/all_views.py`

El CRM base no tiene opinión sobre qué debería propagar validar una venta; las instalaciones sí. El
gancho es una ruta punteada a un callable que recibe `(subscription, user)`:

```python
hook_path = getattr(settings, "SUBSCRIPTION_VALIDATED_HOOK", None)
if not hook_path:
    return None
try:
    from django.utils.module_loading import import_string

    return import_string(hook_path)(subscription, user)
except Exception:
    logger.exception("SUBSCRIPTION_VALIDATED_HOOK failed for subscription %s", ...)
    return None
```

Se llama desde `ValidateSubscriptionSalesRecord.form_valid()`, justo después de
`subscription.validate(user=...)`. Importan dos propiedades: **falla cerrado** —sin el setting no pasa
absolutamente nada— y **nunca levanta excepción**: la validación ya está guardada y es la fuente de
verdad, así que no poder propagarla se loguea y se sigue.

### 2. Quién nace validada y quién lleva registro de venta

**Archivos:** `utopia-crm-ladiaria` (`utils.py`, `views/api.py`), documentado acá porque define la
cola de la que depende esta rama

Las ventas que entran por la web no tienen vendedor detrás, así que no hay nada que validar:
MercadoPago, Witty y la promo por API se crean con `validated=True` y sin registro de venta. La
digital gratis de dos meses sí lo lleva —con precio 0 y el vendedor que la regaló—, porque la da de
alta alguien desde el CRM.

### 3. Una suscripción validada igual se puede comisionar

**Archivo:** `support/views/all_views.py`

Nacer validada no debería cerrar la puerta a comisionar: el caso real es el vendedor que refiere a
una persona que después compra sola. `SalesRecordCreateView` ya no revalida una suscripción que ya
estaba validada — hacerlo pisaba `validated_by`, y `NULL` ahí es justamente la marca de que la validó
el sistema. El botón se llama distinto según el caso: *Registrar venta* cuando la venta está
pendiente, *Comisionar vendedor* cuando la suscripción ya está validada y no tiene registro.

### 4. Las gratuitas no reportan forma de pago ni pagan comisión

**Archivos:** `core/models.py`, `support/models.py`, `support/forms.py`,
`support/templates/sales_record_filter.html`

Los obsequios y las de staff se registran como venta FULL, así que el panel les mostraba la forma de
pago de la suscripción y les calculaba comisión sobre una venta que no movió plata. El criterio vive
en un solo lugar, `Subscription.is_free()` —tipos `"F"` (obsequio) y `"S"` (staff), el mismo par que
`core.forms` ya trata como gratuito—, y `SalesRecord.is_free_subscription()` le delega.
`get_payment_type`, `calculate_total_commission`, `calculate_commission` y `set_commissions` lo leen;
este último escribe 0 explícitamente, para que el valor guardado no pueda alejarse de lo que muestra
el panel ni cuando un manager fuerza el cálculo al validar.

En la pantalla de validación los campos de comisión quedan **bloqueados, no sólo ocultos**:

```python
if self.instance and self.instance.pk and self.instance.is_free_subscription():
    self.initial["can_be_commissioned"] = False
    self.fields["can_be_commissioned"].disabled = True
    self.fields["override_commission_value"].disabled = True
```

`disabled` hace que Django ignore lo que venga en el POST y conserve el valor inicial, así que un
pedido armado a mano tampoco consigue comisión. El inicial hay que pisarlo en `self.initial`, que es
donde un `ModelForm` guarda el valor propio de la instancia.

### 5. El estado de validación se ve en todos los tipos de suscripción

**Archivos:** `support/templates/includes/_subscription_validation_actions.html` (nuevo),
`support/templates/includes/_overview_subscription_list_item.html`

El bloque de validación vivía dentro de la rama `else` de un `if` por `subscription.type`, así que
sólo lo veían las normales. Eso quedó mal cuando las gratuitas pasaron a llevar registro de venta:
entran en la cola y en el badge, pero desde el detalle del contacto no había cómo validarlas (en la
base local son 724 obsequios y 3.650 promos con registro de venta, todas invisibles desde ahí). El
bloque salió a un include propio, usado desde las tres ramas en vez de repetirse, y ahora decide con
`Subscription.is_free()` si corresponde comisionar — las de staff caían en la rama de las normales y
les aparecía una comisión que no pueden pagar.

El cuarto caso —validada **y** con registro— no mostraba nada, así que "está todo en orden" se veía
igual que "no se cargó nada". Ahora muestra una chapita *Validada* con quién y cuándo en el tooltip, o
"por el sistema" cuando `validated_by` es `NULL`.

### 6. Registros de ventas pasa al menú principal, con el pendiente al lado

**Archivos:** `templates/components/_sidebar.html`,
`templates/components/sidebar_items/_campaign_management.html`, `core/templatetags/core_tags.py`

La cola deja de ser un ítem de gestión de campañas y pasa a ser una entrada de primer nivel para
Managers, con un badge. La validación vive en la suscripción y no en el registro, así que el tag
cuenta los registros cuya suscripción sigue sin validar, y es defensivo con la misma forma que
`pending_email_takeovers`: un badge nunca es motivo para que una página no renderice.

## 📁 Archivos modificados

- **`core/utils.py`** — `run_subscription_validated_hook()`
- **`core/models.py`** — `Subscription.is_free()`
- **`core/templatetags/core_tags.py`** — `pending_sales_records()`
- **`support/models.py`** — `SalesRecord.is_free_subscription()` delega en `Subscription.is_free()`;
  forma de pago y comisiones lo respetan
- **`support/forms.py`** — campos de comisión bloqueados para las gratuitas
- **`support/views/all_views.py`** — llamada al gancho al validar; no se revalida al comisionar
- **`support/views/subscriptions.py`** — estado de validación en el contexto de la suscripción
- **`support/templates/…`** — include de acciones de validación, tooltip del panel, pantalla de
  validación
- **`templates/components/…`** — entrada de sidebar y badge
- **`tests/test_subscription_validation.py`** — suite nueva

## 📚 Detalles técnicos

**Por qué un gancho y no una señal.** Un `post_save` sobre `Subscription` se dispararía en cada save,
y la validación es una transición puntual hecha por una vista puntual. El gancho se llama exactamente
donde ocurre la transición, recibe al usuario que la hizo y se configura por instalación — la app base
no trae ningún comportamiento.

**Suscripciones con fecha de inicio futura.** La implementación de ladiaria no las propaga: el
`plan_id` que recibe el CMS lo arma el mismo serializador que usa el CSV nocturno, que filtra
`start_date__lte=hoy`, así que una suscripción futura empujaría un `plan_id` vacío — peor que no
avisar. La levanta el batch de la noche en que arranca, que es lo que ya pasa hoy.

**La cola vieja.** Antes de esta rama, producción tenía ~126.650 suscripciones sin validar, de las que
sólo ~8.700 llevaban registro de venta. El paquete ladiaria agrega
`validate_historic_subscriptions` para cortar esa cola por fecha; ver su devnote.

## 🧪 Pruebas manuales

1. **Validar una venta de call center (camino feliz):**
   - Con `SUBSCRIPTION_VALIDATED_HOOK` configurado, abrir *Registros de ventas*, elegir una venta
     pendiente y validarla.
   - **Verificar:** aparece el mensaje de éxito, la suscripción queda validada con tu usuario y el
     gancho configurado corrió (en la diaria, la persona puede leer en el sitio al instante).

2. **El gancho no está configurado (caso borde):**
   - Sacar `SUBSCRIPTION_VALIDATED_HOOK` de los settings y validar una venta.
   - **Verificar:** la validación se guarda normalmente y no se propaga nada — sin error ni traceback.

3. **Una suscripción de obsequio (caso borde):**
   - Crear un obsequio (`type="F"`) desde el detalle del contacto y abrir su pantalla de validación.
   - **Verificar:** los campos de comisión están deshabilitados; el panel muestra N/A como forma de
     pago y 0 de comisión. Enviar el formulario a mano con `can_be_commissioned=on` tampoco genera
     comisión.

4. **Comisionar una venta web (caso borde):**
   - Tomar una suscripción creada desde la web (nace validada, sin registro de venta) y usar
     *Comisionar vendedor* desde el detalle del contacto.
   - **Verificar:** se crea el registro con el vendedor y la comisión, y `validated_by` sigue en
     `NULL` — la chapita *Validada* sigue diciendo "por el sistema".

## 📝 Notas de despliegue

- No se requieren migraciones.
- Desplegar junto con la rama del mismo nombre de `utopia-crm-ladiaria`.
- **El orden posterior al deploy importa.** Primero cortar la cola vieja con
  `validate_historic_subscriptions` (ladiaria; primero en seco, después `--fix`), y recién entonces
  configurar el gancho en producción:

  ```python
  SUBSCRIPTION_VALIDATED_HOOK = "utopia_crm_ladiaria.services.activation.activate_on_validation"
  ```

  No por riesgo técnico, sino porque el día que se prenda cada validación empieza a dar acceso web de
  verdad — mejor que arranque sobre una cola chica y real que sobre las ~8.700 de arrastre.
- El resto de la configuración de activación (`WEB_ACTIVATE_SUBSCRIBER_URI` / `_ENABLED`, y la
  whitelist de POST) ya está puesta en producción, y el endpoint del CMS está vivo desde el
  2026-08-17.

## 🚀 Mejoras futuras

- Falta la dirección CMS → CRM de la sincronización instantánea (tarea 3 del frente).
- La activación al aprobar un pedido de desduplicación: el código existe, la llamada desde la rama
  *Aprobar* de la cola no. El orden no es negociable —takeover, aplicar el email, activar— o el CMS
  responde `409 contact_id_conflict`.
- Nada le dice al manager, en la pantalla de validación, si la activación web funcionó de verdad. Una
  nota en el registro de venta, o un estado en la suscripción, ahorraría el viaje a los logs.

---

- **Fecha:** 2026-09-08
- **Autor:** Tanya Tree + Claude Opus 5
- **Rama:** desync/validacion-y-activacion
- **Tipo:** Nueva funcionalidad (+ correcciones)
- **Módulos afectados:** Core (Suscripciones, Utils, Template tags), Support (Registros de venta,
  Validación, Sidebar)
