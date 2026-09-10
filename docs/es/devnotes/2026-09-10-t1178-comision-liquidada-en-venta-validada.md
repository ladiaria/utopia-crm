# Mostrar la comisión liquidada en una venta validada

- **Fecha:** 2026-09-10
- **Autora:** Tanya Tree + Claude Opus 5
- **Ticket:** t1178
- **Tipo:** Bug Fix (+ Mejora en la pantalla de validación)
- **Componente:** Support — Registros de ventas, vistas de validación
- **Impacto:** Comisiones, Experiencia de usuario, Confianza en el panel

## 🎯 Resumen

La pantalla de detalle de un registro de venta informaba una comisión de `0` en ventas que ya
estaban validadas, comisionadas y camino a la liquidación del vendedor. El caso que lo destapó fue
una **venta parcial** — un producto agregado a una suscripción existente — cuyo detalle decía:

```text
0 (Tarjeta de crédito) + 0 (1 productos) + 0 (1) + 105 (productos específicos) = 0
```

mientras el listado de registros de ventas, y la liquidación mensual del vendedor, decían `105`.

No había nada mal calculado. Una comisión tiene dos valores legítimos en dos momentos distintos: una
**previsión** antes de que la venta se valide, y un **monto liquidado** después. `SalesRecord` ya
modelaba los dos — `calculate_total_commission()` para la previsión, el campo guardado
`total_commission_value` para lo liquidado — y el template del listado ya elegía el correcto con un
`if subscription.validated`. Al detalle nunca le llegó esa distinción, así que seguía recalculando la
previsión como si todavía no se hubiera decidido nada.

Arreglar el número dejó a la vista el problema siguiente: una cifra liquidada que el desglose no
explica confunde tanto como una cifra equivocada. Así que la pantalla ahora encabeza con el total y,
cuando los componentes no lo justifican, dice **por qué** — y para poder decirlo con honestidad hubo
que empezar a registrar un dato.

## ✨ Cambios

### 1. Una sola definición de "qué cifra corresponde mostrar"

**Archivo:** `support/models.py`

Dos métodos en `SalesRecord` reemplazan el `if` que estaba copiado en los templates:

```python
def is_settled(self):
    return bool(self.subscription and self.subscription.validated)

def get_commission_value(self):
    if self.is_settled():
        return self.total_commission_value
    return self.calculate_total_commission()
```

`calculate_total_commission()` y `total_commission_value` quedan intactos: cada uno sigue siendo
correcto en su propio momento. Lo que cambia es que ninguna pantalla tiene que saber cuál es cuál.

### 2. El total se muestra separado de sus componentes

**Archivos:** `support/models.py`, `support/templates/validate_subscription_sales_record.html`

`get_commission_breakdown()` devuelve los componentes **sin total**, y el template muestra la cifra
sola, en negrita, con el desglose debajo como referencia. Unirlos con un `=` era lo que hacía que la
pantalla vieja afirmara algo falso; ahora no hay ecuación que pueda estar mal.

`calculate_commission()` (desglose y total en una línea) se conserva para usos fuera del panel.

### 3. La pantalla dice por qué, cuando el desglose no explica la cifra

**Archivo:** `support/models.py`

`get_commission_note()` devuelve una frase, o `None` cuando el desglose se explica solo. Cada rama
informa algo que el registro **sabe** — una marca guardada o una regla —, nunca una suposición sacada
de comparar números:

| Situación | Qué dice |
|---|---|
| Suscripción gratuita | Una suscripción gratuita no paga comisión |
| `can_be_commissioned` en falso | Marcada como no comisionable: no entra en la liquidación |
| Sin validar y no es venta completa | Una venta parcial no paga comisión salvo que quien la valide decida lo contrario |
| `commission_overridden` | Monto ingresado a mano al validar |
| Liquidada, calculada, componentes que no dan | Liquidada al validar; los componentes son los de hoy y ya no dan esa cifra — o se comisionó contra la regla habitual, o cambiaron los precios |

### 4. Las sobreescrituras ahora quedan registradas

**Archivos:** `support/models.py`, `support/views/all_views.py`, `support/migrations/0042_salesrecord_commission_overridden.py`

`override_commission_value` es un campo del formulario, no del modelo: se usaba para escribir el
total y después se descartaba. El único rastro que quedaba de una sobreescritura era que el valor
guardado ya no coincidía con la suma de los componentes — que es *también* lo que parece un cambio de
precios posterior, así que el panel no podía distinguir una cosa de la otra y tenía que callarse
sobre las dos.

Un booleano `commission_overridden` lo registra. `set_commissions()` lo apaga cuando calcula una
comisión, así que la marca no puede quedar vieja si una venta se liquida de nuevo.

### 5. Se eliminó una asignación mal escrita

**Archivo:** `support/views/all_views.py`

```python
sales_record.can_be_commisioned = True   # le falta una "s" al campo real
```

El campo es `can_be_commissioned`, así que esto creaba un atributo suelto y no hacía nada. Además era
redundante: `can_be_commissioned` está en los `fields` del formulario de validación, así que el
ModelForm ya había dejado el valor tildado en `form.instance`. Reemplazada por un comentario que lo
aclara.

## 📁 Archivos modificados

- **`support/models.py`** — `is_settled()`, `get_commission_value()`, `get_commission_breakdown()`, `get_commission_note()`; campo `commission_overridden`; `set_commissions()` apaga la marca
- **`support/views/all_views.py`** — registra la sobreescritura; asignación mal escrita eliminada
- **`support/templates/validate_subscription_sales_record.html`** — total en negrita, nota, desglose debajo; el título cambia según `is_settled`
- **`support/templates/sales_record_filter.html`** — usa `get_commission_value`
- **`tests/test_subscription_validation.py`** — `TestCommissionShownAfterValidating`, 12 tests
- **`locale/es/LC_MESSAGES/django.po` / `.mo`** — textos nuevos

## 📁 Archivos creados

- **`support/migrations/0042_salesrecord_commission_overridden.py`**
- **`docs/es/plans/2026-09-10-t1178-comision-detalle-venta-validada.md`** — el análisis detrás de este cambio

## 📚 Detalles técnicos

**Por qué el componente de forma de pago queda en 0 en una venta parcial.**
`calculate_payment_type_commission()` tiene su propio gate `sale_type == FULL`, y es deliberado: la
forma de pago es de la suscripción entera, no de un producto agregado después. La pantalla ya lo dice
("El método de pago solo aplica para ventas completas"). Ese cero no es parte del bug y no se tocó.

**Decimal contra la suma cruda.** `total_commission_value` es un `DecimalField`; los valores de cada
componente vienen de settings como `int`/`float` (`412.5`, `105`). Las comparaciones pasan por
`Decimal(str(...))` para que un `105.00` liquidado coincida con un `105` recalculado, en vez de
informarse como una discrepancia por una diferencia de representación.

**Conocido, fuera de alcance: `commission_for_amount_of_products_sold` no es un campo.**
`calculate_products_count_commission()` lo asigna y `set_commissions()` lo suma al total, pero el
modelo no tiene esa columna — sólo `commission_for_payment_type`, `commission_for_products_sold` y
`commission_for_subscription_frequency`. El total queda bien porque la suma ocurre en memoria justo
después de la asignación, así que hoy no hay plata mal calculada; lo que se pierde es el **desglose
persistido**, al que le falta ese componente. Agregarlo necesita su propia migración y su propio
ticket.

## 🧪 Pruebas manuales

1. **Camino feliz — una venta parcial que se decide comisionar:**
   - Buscar un registro de venta de tipo Parcial cuyo producto tenga comisión por producto específico, todavía sin validar
   - **Verificar:** listado y detalle muestran `0`, y el detalle explica que una venta parcial no comisiona salvo que quien la valide decida lo contrario
   - Validarla con "Puede comisionarse" tildado
   - **Verificar:** las dos pantallas muestran ahora la misma cifra (105 en el caso de referencia), el título dice "Comisión liquidada", el total está en negrita y la nota explica que los componentes ya no dan esa cifra

2. **Caso borde — monto sobreescrito a mano:**
   - Repetir, escribiendo un monto en "Agregar valor de comisión manualmente" (ej. 300)
   - **Verificar:** las dos pantallas muestran 300 y la nota dice que el monto se ingresó a mano — no el texto de "cambiaron los precios"

3. **Caso borde — no comisionable:**
   - Validar con "Puede comisionarse" destildado
   - **Verificar:** la nota dice que el registro está marcado como no comisionable, en vez de un 0 sin explicación

4. **Caso borde — suscripción gratuita:**
   - Abrir el registro de venta de un obsequio o de staff
   - **Verificar:** sin cambios — sin forma de pago, sin comisión, campos bloqueados

5. **Regresión — una venta completa común:**
   - Validar una con el tilde puesto y sin sobreescritura
   - **Verificar:** la cifra es la misma que mostraba esta pantalla antes del cambio, y **no** hay nota: el desglose se explica solo

## 📝 Notas de despliegue

- **Requiere migración:** `support.0042_salesrecord_commission_overridden` — agrega un booleano con
  valor por defecto, sin reescritura de datos ni backfill
- Las ventas validadas **antes** de este deploy no van a quedar marcadas como sobreescritas aunque lo
  hayan sido: ese dato nunca se guardó. Caen en la nota de "los componentes ya no dan esa cifra", que
  es exacta — nombra las dos posibilidades en vez de elegir una
- **Correr `python manage.py compilemessages -l es` en el deploy.** El `.po` está versionado, el
  `.mo` compilado no (`.gitignore`), así que sin ese paso los textos nuevos se ven en inglés
- Sin cambios de settings. Los `SELLER_COMMISSION_*` se leen igual que antes
- No se recalcula nada retroactivamente: las ventas validadas antes ya tienen guardado el
  `total_commission_value` correcto, y eso es lo que ahora muestran

## 🚀 Mejoras futuras

- Agregar el campo faltante `commission_for_amount_of_products_sold` para que el desglose persistido esté completo
- Mostrar los componentes guardados en una venta liquidada en vez de recalcularlos, una vez que exista ese campo
- Registrar **quién** sobreescribió una comisión y cuándo, no sólo que pasó

---

- **Fecha:** 2026-09-10
- **Autora:** Tanya Tree + Claude Opus 5
- **Rama:** t1178
- **Tipo:** Bug Fix (+ Mejora)
- **Módulos afectados:** Support (Registros de ventas, vistas de validación)
