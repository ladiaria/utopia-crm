# t1178 — La comisión de una venta validada se muestra mal en el detalle (+ typo en la validación)

**Repo:** `utopia-crm` — app `support`
**Tipo:** bug de presentación + typo
**Detectado:** 2026-09-10, sobre una venta parcial que agregó un producto a una suscripción existente

## Resumen

El detalle de un registro de venta **ya validado** muestra una comisión de `0` cuando el valor
realmente guardado y liquidado es otro. En el caso que lo destapó — una venta **parcial** que agregó
un producto con comisión propia — el detalle dice

> `0 (Tarjeta de crédito) + 0 (1 productos) + 0 (1) + 105 (productos específicos) = 0`

mientras el listado de registros de ventas muestra **105**, que es lo que va a entrar en la
liquidación del vendedor.

**Las dos cifras que se contradicen no son un error de cálculo: el cálculo está bien.** El problema
es que el detalle nunca deja de mostrar el *preview* de precomisión, incluso después de que la venta
fue validada y comisionada.

## Por qué pasa

`SalesRecord` tiene dos fuentes de verdad para la comisión, y cada una es correcta en su momento:

| | Qué es | Cuándo aplica |
|---|---|---|
| `calculate_total_commission()` (`support/models.py:693`) | **Preview**: lo que se pagaría si se validara ahora sin tocar nada | Antes de validar |
| `total_commission_value` (campo) | **Valor real**, escrito por `set_commissions()` al validar | Después de validar |

El preview devuelve `0` para todo lo que no sea venta completa:

```python
def calculate_total_commission(self):
    if self.sale_type == self.SALE_TYPE.FULL and not self.is_free_subscription():
        value = (...)
        return value
    return 0
```

Eso es correcto **como preview**: una parcial no comisiona por defecto. Pero quien valida puede
decidir que sí, dejando tildado "Puede comisionarse", y entonces corre `set_commissions(force=True)`
(`support/views/all_views.py:3289`), donde el `force` saltea el gate de `sale_type` y guarda la suma
de los cuatro componentes — que para una parcial suele ser sólo el de productos específicos.

**El listado ya resuelve esto bien** (`support/templates/sales_record_filter.html:181-185`):

```django
{% if sr.subscription.validated %}
  <td>{{ sr.total_commission_value }}</td>
{% else %}
  <td>{{ sr.calculate_total_commission }}</td>
{% endif %}
```

**El detalle no** (`support/templates/validate_subscription_sales_record.html:404`): llama siempre a
`object.calculate_commission`, que arma el desglose componente por componente y cierra con
`calculate_total_commission()`. Le falta exactamente la misma distinción.

Por eso la secuencia que se ve desde afuera es coherente aunque parezca un salto:

- parcial sin validar → listado 0 (preview), detalle 0 (preview) ✔
- parcial validada → listado **105** (guardado), detalle **0** (preview) ✘ ← acá está el bug

## Comportamiento esperado

Una vez que la suscripción está validada, **el detalle debe mostrar el valor guardado**, no el
preview. Concretamente:

1. Si `subscription.validated`, la línea "Comisión calculada" muestra `total_commission_value`.
2. El desglose por componentes (`calculate_commission()`) sigue siendo útil como explicación de
   *de dónde salió* la plata, así que conviene conservarlo — pero el total que cierra la línea tiene
   que ser el guardado, no el recalculado. Alternativa: etiquetarlo explícitamente como
   "Comisión liquidada: N" y dejar el desglose abajo como detalle informativo.
3. Cuidado con el caso `override_commission_value`: cuando se pisó el monto a mano, el guardado
   tampoco coincide con la suma de los componentes. Un desglose que "no da" la cifra final es
   esperable ahí, y la pantalla debería decirlo en vez de dejar al lector sacando la cuenta.
4. El `0 (Tarjeta de crédito)` **no se toca**: `calculate_payment_type_commission()`
   (`support/models.py:592`) tiene su propio gate `sale_type == FULL` y es coherente con el cartel
   "El método de pago solo aplica para ventas completas" que ya está en la pantalla.

## Segundo problema: typo en `form_valid`

`support/views/all_views.py:3282`:

```python
if form.cleaned_data["can_be_commissioned"]:
    sales_record.can_be_commisioned = True   # ← falta una "s": commisioned
```

Está creando un atributo fantasma en la instancia; el campo real del modelo es
`can_be_commissioned`. Hoy no rompe nada porque `can_be_commissioned` está en los `fields` del
`SalesRecordValidationForm` (`support/forms.py:902`), así que el ModelForm ya dejó el valor correcto
en `form.instance` antes de llegar a esa línea. Es una línea que no hace lo que dice y que va a
morder a quien la lea como si funcionara.

**Fix:** borrar la línea (es redundante con el ModelForm) o corregir la ortografía. Preferible
borrarla y dejar un comentario de por qué el ModelForm ya se encarga.

## Verificación

- Tomar una venta parcial sin validar, tildar "Puede comisionarse", validar: listado y detalle
  tienen que decir lo mismo.
- Repetir con `override_commission_value` cargado a mano: ambas pantallas muestran el override.
- Venta completa validada: sin cambios respecto de hoy.
- Suscripción gratuita: sigue mostrando "Suscripción gratuita: sin comisión" y 0.

## Archivos

- `support/templates/validate_subscription_sales_record.html:402-409`
- `support/models.py:663` (`calculate_commission`), `:693` (`calculate_total_commission`)
- `support/views/all_views.py:3282`
- Referencia de cómo se hace bien: `support/templates/sales_record_filter.html:181-185`

## Tercer hallazgo: `commission_for_amount_of_products_sold` no es un campo

`calculate_products_count_commission()` (`support/models.py:586`) asigna
`self.commission_for_amount_of_products_sold`, y `set_commissions()` lo suma al total. Pero **ese
atributo no existe en el modelo**: los campos son `commission_for_payment_type`,
`commission_for_products_sold` y `commission_for_subscription_frequency`.

El total queda bien porque la suma ocurre en memoria justo después de la asignación, así que hoy no
hay plata mal calculada. Lo que se pierde es el **desglose persistido**: de los cuatro componentes,
el de cantidad de productos nunca se guarda. Si alguna vez se quiere mostrar o auditar el desglose
tal como quedó al validar (en vez de recalcularlo, que es justamente lo que este ticket corrige),
ese componente no va a estar.

**Fuera del alcance de t1178**: agregar el campo requiere migración en el repo base. Queda anotado
para su propio ticket.

## Tests sugeridos

En `tests/test_subscription_validation.py`:

1. `test_validated_partial_sale_detail_shows_stored_commission` — parcial forzada a comisionar,
   el contexto/render del detalle muestra el guardado y no 0.
2. `test_validated_sale_with_override_shows_override` — con `override_commission_value`.
3. `test_unvalidated_sale_still_shows_preview` — no romper el comportamiento previo a validar.


## Estado

**Implementado** en la rama `t1178` de `utopia-crm` (sin mergear).

- `is_settled()` y `get_commission_value()` nuevos en `SalesRecord`: una sola definición de "qué
  cifra corresponde mostrar", en vez del `if` repetido en cada template. El listado pasa a usarla
  (mismo resultado que antes, una sola fuente).
- `get_commission_breakdown()` devuelve los componentes **sin total**, y la pantalla de validación
  muestra el total solo, en negrita, con el desglose debajo. Al separarlos desaparece el `=` que
  podía afirmar algo falso.
- `get_commission_note()` explica la cifra cuando el desglose no alcanza: no comisionable, parcial
  que todavía no comisiona, monto ingresado a mano, o componentes que ya no dan esa cifra. Cada
  rama informa algo que el registro **sabe**; ninguna adivina comparando números.
- **Campo nuevo `commission_overridden`** (migración `support.0042`). Sin él, una sobreescritura era
  indistinguible de un cambio de precios posterior: las dos se ven como "el guardado no coincide con
  la suma". Inferirlo hubiera sido el mismo pecado que este ticket corrige.
- La etiqueta del detalle dice "Comisión liquidada" cuando ya está validada.
- Borrada la línea del typo `can_be_commisioned`.
- 12 tests nuevos en `tests/test_subscription_validation.py` (`TestCommissionShownAfterValidating`),
  incluido uno que verifica que listado y detalle informan la misma cifra antes y después de validar.
- Traducciones agregadas a `locale/es` y verificadas una por una. El `.mo` está gitignoreado:
  **hay que correr `compilemessages` en el deploy**.

**Ojo en el deploy:** las ventas validadas antes de este cambio no quedan marcadas como
sobreescritas aunque lo hayan sido — ese dato nunca se guardó. Caen en la nota de "los componentes
ya no dan esa cifra", que nombra las dos posibilidades en vez de elegir una.
