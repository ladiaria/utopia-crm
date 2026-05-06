# t1139 — Subscription: campo `cached_price`

## Objetivo

Agregar un campo `cached_price` en el modelo `Subscription` que se mantiene
actualizado automáticamente, para eliminar las N×4-5 queries en vistas que
muestran listas de suscripciones con sus precios (ej: `salary_subscriptions`).

## ¿Siempre queda correcto el cache?

Sí, **si se capturan todos los triggers de invalidación**. Hay tres categorías:

### Triggers directos (fáciles — via Django signals)

| Evento | Signal | Acción |
|---|---|---|
| Se agrega/modifica/borra un `SubscriptionProduct` | `post_save` / `post_delete` en `SubscriptionProduct` | Recalcular `cached_price` de `instance.subscription` |
| Cambia `frequency` de la suscripción | `pre_save` en `Subscription` (detectar cambio) + `post_save` | Recalcular `cached_price` |

### Triggers en cascada (moderados — pueden afectar muchas suscripciones)

| Evento | Signal | Acción |
|---|---|---|
| Cambia el precio (`price`) de un `Product` | `post_save` en `Product` | Recalcular `cached_price` de todas las suscripciones que tienen ese producto |
| Cambia `billing_mode`, `has_implicit_discount`, o `target_product` de un `Product` | `post_save` en `Product` | Ídem |

Para este caso se recomienda una **tarea asincrónica** (Celery task o management
command) en lugar de hacerlo en el mismo `post_save`, porque puede ser costoso.

### Triggers globales (difíciles — invalidan todo)

| Evento | Acción recomendada |
|---|---|
| Se activa/desactiva una `PriceRule` o cambia su configuración | Invalidan potencialmente **todas** las suscripciones. Opciones: (a) marcar `cached_price=None` en todas y recalcular en background, (b) aceptar staleness temporal y recalcular via cron |

**Recomendación:** Para PriceRules, usar un cron nocturno de refresco completo
en lugar de intentar invalidación quirúrgica — las PriceRules cambian raramente
y un recalculo full nocturno es manejable.

## Archivos relevantes

| Archivo | Qué toca |
|---|---|
| `utopia-crm/core/models.py:2157-2192` | `Subscription.product_summary()` y `get_price_for_full_period()` |
| `utopia-crm/core/models.py:1870-1930` | `Subscription.add_product()` / `remove_product()` |
| `utopia-crm/core/signals.py` | Signals existentes de Subscription |
| `utopia-crm-ladiaria/utopia_crm_ladiaria/signals.py` | Signals de ladiaria (tiene `subscriptionproduct_pre_save_signal`) |
| `utopia-crm-ladiaria/utopia_crm_ladiaria/templates/salary_subscriptions.html:70` | Template — usa `get_price_for_full_period` |
| `utopia-crm/support/templates/contact_detail/tabs/includes/_subscription_card.html:66,68` | Template — usa `get_price_for_full_period` y `get_price_for_full_period_with_pauses` |
| `utopia-crm-ladiaria/utopia_crm_ladiaria/views/subscriptions.py:1233` | `ladiaria_product_change()` — calcula diferencia de precio |
| `utopia-crm-ladiaria/utopia_crm_ladiaria/views/retention.py:95` | Retention — calcula diferencia de precio |

## Plan de implementación

### Paso 1 — Agregar campo al modelo base

En `utopia-crm/core/models.py`, en el modelo `Subscription`:

```python
cached_price = models.DecimalField(
    max_digits=10, decimal_places=2, null=True, blank=True, db_index=False
)
```

`null=True` para poder migrar sin romper nada. El valor `None` significa
"no calculado todavía" — las vistas deben manejar este caso con fallback
a `get_price_for_full_period()`.

### Paso 2 — Migration en utopia-crm

```bash
python manage.py makemigrations --settings=migration_settings core
```

### Paso 3 — Método helper en Subscription

```python
def get_cached_or_real_price(self):
    """Returns cached_price if available, otherwise calculates on the fly."""
    if self.cached_price is not None:
        return self.cached_price
    return self.get_price_for_full_period()

def refresh_cached_price(self):
    """Recalculates and saves cached_price. Call after product changes."""
    self.cached_price = self.get_price_for_full_period()
    self.save(update_fields=['cached_price'])
```

### Paso 4 — Signals para invalidación automática

Agregar en `utopia-crm/core/signals.py` (o crear archivo dedicado):

```python
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

@receiver(post_save, sender=SubscriptionProduct)
@receiver(post_delete, sender=SubscriptionProduct)
def invalidate_subscription_cached_price_on_product_change(sender, instance, **kwargs):
    sub = instance.subscription
    sub.cached_price = sub.get_price_for_full_period()
    sub.save(update_fields=['cached_price'])

# Para detectar cambio de frequency:
@receiver(pre_save, sender=Subscription)
def detect_subscription_frequency_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Subscription.objects.get(pk=instance.pk)
            instance._frequency_changed = old.frequency != instance.frequency
        except Subscription.DoesNotExist:
            instance._frequency_changed = True
    else:
        instance._frequency_changed = True  # nueva suscripción

@receiver(post_save, sender=Subscription)
def recalculate_on_frequency_change(sender, instance, created, **kwargs):
    if created or getattr(instance, '_frequency_changed', False):
        price = instance.get_price_for_full_period()
        if price != instance.cached_price:
            Subscription.objects.filter(pk=instance.pk).update(cached_price=price)
```

**Nota:** El signal de `post_save` en Subscription usa `update_fields` con
`objects.filter().update()` para evitar recursión infinita (no dispara `post_save`
de nuevo).

### Paso 5 — Signal para cambios en Product (invalidación en cascada)

Agregar en `utopia-crm/core/signals.py`:

```python
PRICE_AFFECTING_FIELDS = {'price', 'billing_mode', 'has_implicit_discount', 'target_product'}

@receiver(pre_save, sender=Product)
def detect_product_price_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Product.objects.get(pk=instance.pk)
            instance._price_fields_changed = any(
                getattr(old, f) != getattr(instance, f) for f in PRICE_AFFECTING_FIELDS
            )
        except Product.DoesNotExist:
            instance._price_fields_changed = False

@receiver(post_save, sender=Product)
def invalidate_subscriptions_on_product_change(sender, instance, **kwargs):
    if getattr(instance, '_price_fields_changed', False):
        # Marcar como None (stale) — un cron o management command recalcula en background
        Subscription.objects.filter(
            subscriptionproduct__product=instance
        ).update(cached_price=None)
```

Esto marca el cache como stale (`None`) en lugar de recalcular de forma síncrona
(que podría ser miles de suscripciones). Las vistas con fallback a
`get_cached_or_real_price()` siguen funcionando con el cálculo real mientras se
repopula.

### Paso 6 — Management command para refresco masivo

Crear `utopia-crm/core/management/commands/refresh_subscription_cached_prices.py`:

```python
# Recalcula cached_price para todas las suscripciones con cache None/stale.
# Usar: python manage.py refresh_subscription_cached_prices [--all]
# Correr en cron nocturno o manualmente después de cambios en PriceRules/Products.
```

Implementación: iterar en batches de 100-500 suscripciones con `prefetch_related(
'subscriptionproduct_set__product')` para minimizar queries.

### Paso 7 — Poblado inicial

Correr el management command con `--all` para poblar `cached_price` en todas las
suscripciones existentes antes de activar las vistas.

### Paso 8 — Actualizar vistas y templates

- `salary_subscriptions.html:70`: `{{ subscription.get_price_for_full_period }}`
  → `{{ subscription.get_cached_or_real_price }}`
- `_subscription_card.html:66,68`: ídem (solo para `get_price_for_full_period`;
  `get_price_for_full_period_with_pauses` no tiene cache todavía — dejar como está)
- Views que calculan diferencia de precio (`ladiaria_product_change`, `retention`):
  seguir usando `get_price_for_full_period()` directamente — ahí se necesita el
  valor exacto y actualizado, no el cache.

### Paso 9 — Cron nocturno para PriceRules

Configurar un cron o scheduled task que corra:
```bash
python manage.py refresh_subscription_cached_prices
```

Esto asegura que incluso si una PriceRule cambia y el cache queda stale,
al día siguiente queda correcto.

## Consideraciones de testing

- Unit test: crear SubscriptionProduct, verificar que `cached_price` se actualiza.
- Unit test: borrar SubscriptionProduct, verificar que `cached_price` se actualiza.
- Unit test: cambiar `frequency`, verificar que `cached_price` se actualiza.
- Unit test: cambiar `Product.price`, verificar que `cached_price` queda `None`.
- Test del management command: después de correrlo, ninguna suscripción tiene `None`.
- Test de `get_cached_or_real_price()`: con cache None, devuelve el precio real.

```bash
python -W ignore manage.py test --settings=test_settings --keepdb tests.test_subscription
python -W ignore manage.py test --settings=test_settings --keepdb utopia_crm_ladiaria.tests.test_billing
```

## Decisiones de diseño a confirmar

1. **¿El campo va en utopia-crm o utopia-crm-ladiaria?**
   Recomendado: en `utopia-crm/core` (base). Los signals también van en el base
   si afectan modelos base. Esto da acceso a `cached_price` desde cualquier contexto.

2. **¿Recalculo síncrono o asíncrono en signals de SubscriptionProduct?**
   El plan propone síncrono (inmediato). Si hay suscripciones con muchos productos,
   puede agregar latencia en saves. Evaluar en staging con datos reales.

3. **¿Invalidar o recalcular en cascada de Product?**
   El plan propone invalidar (poner `None`) para evitar bloqueos en cascada.
   Si hay Celery disponible, se puede cambiar a tarea async que recalcula.

## Impacto esperado

- `salary_subscriptions`: de N×4-5 queries a 0 queries extra por precio
- Cualquier futura vista de lista de suscripciones: beneficio automático
- Costo: un campo extra en la tabla `core_subscription` y signals adicionales
