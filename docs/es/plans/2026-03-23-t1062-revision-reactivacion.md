# Plan: Revision de la funcionalidad de reactivación de suscripciones (Trello: t1062)

**Responsable:** @tanyatree · **Estado:** ✅ Implementado · **Actualizado:** 2026-03-23

## Contexto pedido

Cuando se reactiva una suscripción, se debe poder ver y editar el método de pago. Además, revisar que se esté cumpliendo la regla de correr la fecha de próxima facturación la misma cantidad de días que la suscripción estuvo inactiva.

## Complemento

La función a revisar es la de reactivación de suscripciones. Se encuentra en utopia-crm/support/views/subscriptions.py y se llama reactivate_subscription.

El template no muestra la forma de pago. Se pide agregar o bien la forma de pago en la tabla donde se listan los campos de la suscripción o convertir esa tabla en un formulario editable donde ahí se encuentre la forma de pago y al momento de reactivar la suscripción, se actualice el método de pago.

Se pide también que se cumpla la regla de correr la fecha de próxima facturación la misma cantidad de días que la suscripción estuvo inactiva para lo cual se puede utilizar la fecha de fin de la suscripción. Entiendo que si esta está en el pasado deberíamos correr la fecha de próxima facturación una cantidad de días igual a la diferencia entre la fecha de fin y la fecha actual para que el cliente no tenga que pagar nada en ese periodo.

## Implementación (@claude, 2026-03-23)

### Archivos modificados

- `utopia-crm/support/views/subscriptions.py` — función `reactivate_subscription`
- `utopia-crm/support/templates/reactivate_subscription.html`

### Método de pago editable

Se importaron `PaymentMethod` y `PaymentType` desde `core.models`. En el contexto GET se pasan los querysets `payment_methods` y `payment_types` (filtrados por `active=True`). En el template se agregaron dos `<select>` dentro del formulario de confirmación, con los valores actuales de la suscripción preseleccionados. En el POST se leen los IDs enviados y se asignan a `subscription.payment_method_fk_id` / `subscription.payment_type_fk_id` antes del `save()`. Un valor vacío limpia el campo (pone `None`).

La tabla de detalles también muestra los valores actuales de `payment_method_fk` y `payment_type_fk` como referencia.

### Corrección de la fecha de próxima facturación

Se reemplazó la lógica anterior (`next_billing = today + 1 día`) por el corrimiento correcto:

```python
inactive_days = (date.today() - inactive_end_date).days
subscription.next_billing += timedelta(days=inactive_days)
```

Se captura `end_date` en `inactive_end_date` antes de limpiarlo. La condición aplica siempre que `end_date < today`, sin importar si `next_billing` ya estaba en el pasado o en el futuro — en ambos casos se corre hacia adelante la misma cantidad de días que estuvo inactiva la suscripción.

En el template se muestra la fecha proyectada (`new_next_billing`) junto a la actual, con una leyenda "(adjusted for inactive period)".
