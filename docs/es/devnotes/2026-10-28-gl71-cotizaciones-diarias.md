# Tabla de cotizaciones diarias

- **Fecha:** 2026-10-28
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl71-cotizaciones-bcu
- **Tipo:** Funcionalidad
- **Componente:** Invoicing (modelos, admin, comandos de gestión)
- **Impacto:** Modelo de datos, nuevo cron, settings nuevos

## 🎯 Resumen

Las facturas en moneda extranjera necesitan la cotización que corresponde al día en que se emiten, y tiene que ser la
misma que usa la autoridad fiscal. Este cambio pone la base: una tabla `ExchangeRate` con una fila por moneda y día,
una función `get_exchange_rate(currency, for_date)` que devuelve la cotización del día hábil anterior, y un comando
`update_exchange_rates` que carga las cotizaciones todos los días desde una fuente que pone cada instalación, porque
dónde se publica la cotización oficial depende del país. Todavía ninguna factura la usa: la moneda en las facturas
llega en un cambio posterior. Es parte de las suscripciones en dólares de la diaria cobradas por PayPal
(it/utopia-crm-ladiaria#64, #71), cuyo paquete de customización pone como fuente al Banco Central del Uruguay.

## ✨ Cambios

### 1. El modelo `ExchangeRate`

**Archivos:** `invoicing/models.py`, `invoicing/migrations/0032_exchangerate.py`

Una fila por moneda (código ISO 4217) y día, única por `(currency, date)`, con la cotización (`rate`) tal como la
publica la fuente (`DecimalField(12, 6)`), la fuente (`source`) que la cargó y `created_at`. Sólo tienen fila los días
que la fuente publica, así que la tabla es también la historia de qué cotización correspondía a cada fecha.

### 2. Qué cotización corresponde a una fecha

**Archivo:** `invoicing/exchange_rates.py`

`get_exchange_rate(currency, for_date)` devuelve la última cotización **anterior** a `for_date`. Las fuentes oficiales
sólo publican en días hábiles, así que la fila anterior ya es la del día hábil anterior: los fines de semana y los
feriados se saltean sin mantener ningún calendario.

Lanza `ExchangeRateNotAvailable` si no hay cotización anterior, o si tiene más de `EXCHANGE_RATE_MAX_AGE_DAYS` días
corridos (6 por defecto). Un documento emitido con una cotización vieja estaría mal, así que es mejor que espere a que
se cargue.

### 3. La fuente, que pone cada instalación

**Archivo:** `invoicing/exchange_rates.py`

`EXCHANGE_RATE_SOURCE` es la ruta con puntos de un callable `(currency, date_from, date_to)` que devuelve pares
`(date, rate)`, uno por día publicado en el rango, con los dos extremos incluidos. Su atributo opcional `source_name`
se guarda en las filas que carga. No tiene valor por defecto: el repo base no elige un país.

### 4. El comando `update_exchange_rates`

**Archivo:** `invoicing/management/commands/update_exchange_rates.py`

Para cada moneda de `EXCHANGE_RATE_CURRENCIES` (o de `--currency`), trae los últimos `--days` días (10 por defecto) y
crea las filas que faltan, así que un día en que la fuente falló se recupera al siguiente. Nunca pisa una fila
existente: si alguna no coincide con la fuente (por ejemplo, una cotización cargada a mano), lo informa. Al final
verifica que esté disponible la cotización para el día de hoy, así que conviene correrlo antes de facturar.

Sin `EXCHANGE_RATE_CURRENCIES` no hace nada. Con monedas pero sin `EXCHANGE_RATE_SOURCE`, falla diciéndolo.

Como `close_lost_schedule_activities`, con `--verbosity 0` sólo imprime anomalías, y termina con error si hay alguna,
así un cron sólo manda mail cuando algo necesita atención.

### 5. Admin

**Archivo:** `invoicing/admin.py`

`ExchangeRateAdmin` lista las cotizaciones por moneda y fecha. Cargar una cotización acá es el respaldo cuando falla
la fuente; su `source` es `manual`.

## 📁 Archivos modificados

- **`invoicing/models.py`** — Modelo `ExchangeRate`.
- **`invoicing/admin.py`** — `ExchangeRateAdmin`.
- **`locale/es/LC_MESSAGES/django.po`** — Traducciones al español de los textos nuevos.
- **`CHANGELOG.md`** — Entrada de este cambio.

## 📁 Archivos creados

- **`invoicing/exchange_rates.py`** — `get_exchange_rate`, `ExchangeRateNotAvailable` y `get_exchange_rate_source`.
- **`invoicing/management/commands/update_exchange_rates.py`** — La carga diaria.
- **`invoicing/migrations/0032_exchangerate.py`** — Crea la tabla y su restricción de unicidad.
- **`tests/test_exchange_rates.py`** — Regla del día hábil anterior, antigüedad máxima, y el comando con una fuente
  simulada.

## 📚 Detalles técnicos

**Settings:**

```python
EXCHANGE_RATE_CURRENCIES = ["USD"]  # Por defecto: [] (el comando no hace nada).
EXCHANGE_RATE_SOURCE = "mypackage.exchange_rates.fetch"  # Sin valor por defecto; obligatorio con monedas.
EXCHANGE_RATE_MAX_AGE_DAYS = 6  # Por defecto.
```

**Una fuente** es cualquier función con esta forma:

```python
def fetch(currency, date_from, date_to):
    return [(date(2026, 10, 23), Decimal("40.078")), (date(2026, 10, 26), Decimal("40.214"))]


fetch.source_name = "mysource"
```

No tiene que devolver nada para los días que no publica (un rango con sólo un fin de semana devuelve `[]`), y tiene que
lanzar una excepción ante una falla real: el comando informa la excepción y sigue con la próxima moneda.

**Por qué 6 días.** Los feriados bancarios largos dejan huecos entre días publicados: en Uruguay, Carnaval (lunes y
martes son feriados bancarios, así que el miércoles usa la cotización del viernes, de hace 5 días). 6 deja un día de
margen y sigue fallando cuando la carga diaria dejó de funcionar.

**Por qué una tabla y no un setting o una variable.** Un único valor pierde la historia: no se podría saber qué
cotización correspondía a una fecha, ni auditar un documento después.

## 🧪 Pruebas manuales

1. **Carga diaria (camino feliz):**
   - Con `EXCHANGE_RATE_CURRENCIES = ["USD"]` y `EXCHANGE_RATE_SOURCE` configurado, correr
     `python manage.py update_exchange_rates`.
   - **Verificar:** imprime una línea "cargada" por cada día publicado de los últimos 10 días, y las cotizaciones
     aparecen en el admin, en Invoicing → Cotizaciones, con el nombre de la fuente. Correrlo de nuevo no carga ni
     imprime nada.

2. **Día hábil anterior:**
   - En `python manage.py shell`, correr `get_exchange_rate("USD", <un lunes>)`.
   - **Verificar:** devuelve la cotización del viernes anterior.

3. **Caso borde — una cotización manual que no coincide:**
   - En el admin, cambiar la cotización de uno de los días cargados y volver a correr el comando.
   - **Verificar:** el comando informa ese día como anomalía, termina con error, y la fila conserva el valor manual.

4. **Caso borde — cotizaciones viejas:**
   - Con la tabla vacía, correr `python manage.py update_exchange_rates --currency USD --days 0`.
   - **Verificar:** informa que no hay cotización de USD anterior a hoy y termina con error: la cotización del propio
     día, aunque ya esté publicada, no es la que corresponde a hoy.

5. **Caso borde — sin fuente:**
   - Sacar `EXCHANGE_RATE_SOURCE` y correr `python manage.py update_exchange_rates --currency USD`.
   - **Verificar:** falla diciendo que `EXCHANGE_RATE_SOURCE` no está configurado.

## 📝 Notas de despliegue

- **Se requieren migraciones:** `invoicing.0032_exchangerate`.
- **Recompilar traducciones:** `python manage.py compilemessages -l es`.
- Para usarlo, configurar `EXCHANGE_RATE_CURRENCIES` y `EXCHANGE_RATE_SOURCE`, y agregar
  `update_exchange_rates --verbosity 0` al cron, de madrugada y antes de la facturación.
- Sin `EXCHANGE_RATE_CURRENCIES`, no cambia nada.

## 🚀 Mejoras futuras

- `currency` y la `exchange_rate` del momento de emisión en las facturas, tomada de `get_exchange_rate` al crear la
  factura.

## 🎓 Decisiones de diseño

- **La fuente vive fuera del repo base.** Qué cotización es la oficial, y dónde se publica, depende del país y de la
  autoridad fiscal; el repo base se queda con lo que comparten todas las instalaciones (la tabla, la regla del día hábil
  anterior, la carga diaria) y deja que cada una enchufe su fuente.
- **Las filas nunca se pisan.** Una vez que una cotización se usó para emitir un documento, cambiarla en silencio haría
  que la tabla no coincida con los documentos. La diferencia se informa y decide una persona.

---

- **Fecha:** 2026-10-28
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl71-cotizaciones-bcu
- **Tipo:** Funcionalidad
- **Módulos afectados:** Invoicing
