# t1138 — PaymentRequest: campo `price` snapshot

## Objetivo

Eliminar las N×4-5 queries extra que ocurren en vistas de lista de PaymentRequests
(seller_pending_payment_requests, manager_payment_requests) al llamar
`get_subscription_price()` por cada fila. En su lugar, guardar el precio calculado
en el momento de creación del PaymentRequest.

## Motivación de negocio

El precio de un PaymentRequest **debería ser inmutable** una vez emitido: representa
lo que se le cobrará al suscriptor en ese período. Si la suscripción cambia después
(producto distinto, frecuencia nueva), el PaymentRequest histórico debe reflejar
el precio original, no el nuevo. Un snapshot es semánticamente correcto además de
performante.

## Archivos relevantes

| Archivo | Qué toca |
|---|---|
| `utopia-crm-ladiaria/utopia_crm_ladiaria/models.py:255-380` | Modelo PaymentRequest |
| `utopia-crm-ladiaria/utopia_crm_ladiaria/views/__init__.py:2489-2569` | Vistas seller_pending y manager |
| `utopia-crm-ladiaria/utopia_crm_ladiaria/templates/seller_pending_payment_requests.html:102` | Template — usa `get_subscription_price` |
| `utopia-crm-ladiaria/utopia_crm_ladiaria/templates/manager_payment_requests.html:79` | Template — usa `get_subscription_price` |
| `utopia-crm-ladiaria/utopia_crm_ladiaria/utils.py:210-257` | `create_mp_subscription_for_contact()` — crea PaymentRequests |

## Plan de implementación

### Paso 1 — Agregar campo al modelo

En `utopia_crm_ladiaria/models.py`, agregar en `PaymentRequest`:

```python
price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
```

`null=True` permite migrar sin romper registros existentes.

### Paso 2 — Migration

```bash
python manage.py makemigrations --settings=migration_settings utopia_crm_ladiaria
```

### Paso 3 — Poblar al crear PaymentRequest

Todos los lugares donde se crea un PaymentRequest deben calcular y guardar el precio:

**Opción A (recomendada): override de `save()`**

```python
def save(self, *args, **kwargs):
    if self.price is None and self.subscription_id:
        self.price = self.subscription.get_price_for_full_period()
    super().save(*args, **kwargs)
```

Esto cubre automáticamente cualquier creación futura sin tener que recordar
poblarlo en cada vista/comando.

**Importante:** usar `self.price is None` (no `not self.price`) para no
sobrescribir un precio de cero si alguna vez existiera.

### Paso 4 — Poblar registros existentes (data migration)

Crear una migration de datos (o management command) para poblar `price` en
PaymentRequests históricos:

```python
for pr in PaymentRequest.objects.filter(price__isnull=True).select_related(
    'subscription'
).prefetch_related('subscription__subscriptionproduct_set__product'):
    pr.price = pr.subscription.get_price_for_full_period()
    pr.save(update_fields=['price'])
```

Hacerlo en batches si hay muchos registros (usar `.iterator()` o paginación manual).

### Paso 5 — Actualizar vistas y templates

En los templates, reemplazar `{{ payment_request.get_subscription_price }}`
por `{{ payment_request.price }}`.

En el export CSV de `manager_payment_requests` (views/__init__.py:2555),
reemplazar `pr.get_subscription_price()` por `pr.price`.

### Paso 6 — Mantener `get_subscription_price()` por compatibilidad

No borrar el método — puede seguir siendo útil para consultas puntuales (ej: detail
view de un PaymentRequest individual). Solo dejar de llamarlo en contextos de lista.

## Consideraciones de testing

- Verificar que el precio guardado coincide con `get_subscription_price()` para
  PaymentRequests nuevos.
- Verificar que el precio histórico NO cambia si se modifica la suscripción después.
- Test de la data migration: todos los PaymentRequests existentes deben tener `price`
  no nulo después de correrla.
- Ejecutar tests existentes de billing:
  ```bash
  python -W ignore manage.py test --settings=test_settings --keepdb utopia_crm_ladiaria.tests.test_billing
  ```

## Impacto esperado

- Vista `seller_pending_payment_requests` (paginada a 50): de ~250 queries a ~5
- Vista `manager_payment_requests` (paginada a 25): de ~125 queries a ~5
- Export CSV: de N×4-5 queries a 1 query
