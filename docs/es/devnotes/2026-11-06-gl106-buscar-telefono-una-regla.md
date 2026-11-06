# Una sola regla para todos los buscadores de teléfono

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#106
- **Tipo:** Corrección de errores
- **Componente:** Core, Support, Invoicing
- **Impacto:** Experiencia de usuario

## 🎯 Resumen

Los números se guardan con el código de país, y los buscadores miran si lo escrito está dentro del número guardado. Entonces `099123456` no es parte de `+59899123456`, y la forma más natural de escribir un número en Uruguay no encontraba a nadie. Con espacios tampoco. «Buscar contactos existentes» ya resolvía el 0 inicial, con código propio. Ahora una sola regla en `core/utils.py` sirve a todos los buscadores donde escribe una persona.

## ✨ Cambios

### 1. La regla

**Archivo:** `core/utils.py`

`phone_search_forms` recibe lo escrito y devuelve las formas a buscar:

| Escrito | Formas |
| --- | --- |
| `099123456` | `099123456`, `99123456` |
| `+59899123456` | `59899123456` |
| `099 123 456` | `099123456`, `99123456`, `099 123 456` |
| `0123` | `0123` |
| `+`, `N/A` | ninguna: no encuentra nada |

- **Sin los ceros sólo con 7 dígitos o más** (`MIN_PHONE_SEARCH_DIGITS`, el mínimo que ya tenía «Buscar contactos existentes»). Si no, `0123` buscaría `123` en todos los números.
- **Tal como se escribió, si tiene símbolos:** algunos números viejos están guardados con espacios, como `062 2 0308`.
- **Sin dígitos, nada:** una forma vacía coincidiría con todos los contactos.

### 2. Dos formas de usarla

**Archivo:** `core/utils.py`

- **`phone_search_q`**, para los buscadores que sólo buscan teléfonos.
- **`phone_or_text_search_q`**, para los que también buscan nombres, emails o documentos. Si el texto no parece un número queda literal, como antes: sacarle los dígitos a `Ana2` buscaría `2` en todos los números.

### 3. Los buscadores que la usan

**Archivos:** `core/filters.py`, `support/filters.py`, `invoicing/filters.py`, `support/views/contacts.py`

- **Lista de contactos y búsqueda de contactos (`apply_main_filter`):** cambian sólo los campos de teléfono. Un número con espacios ya no va por el camino de los nombres, e `id_document` e `id` siguen recibiendo el texto tal cual, así que `0123` sigue encontrando documentos.
- **Tareas programadas (`by_contact_data`) y facturas (`filter_by_contact_phone`):** la misma regla, en los campos que ya buscaba cada uno.
- **`CheckForExistingContactsView`:** deja su copia y usa la regla y el mínimo compartidos.

## 📁 Archivos Modificados

- **`core/utils.py`** — La regla, su mínimo y los dos filtros
- **`core/filters.py`** — Buscador de contactos
- **`support/filters.py`** — Buscador de tareas programadas
- **`invoicing/filters.py`** — Buscador de facturas
- **`support/views/contacts.py`** — Buscar contactos existentes usa la regla
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`tests/test_phone_search.py`** — La regla y los tres buscadores de este repo

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - En la lista de contactos, buscar un número que exista escrito como `099…`, y después como `099 123 456`.
   - **Verificar:** El contacto aparece las dos veces.

2. **Caso borde, parte de un documento:**
   - Buscar `0123`.
   - **Verificar:** Encuentra documentos y números que contienen `0123`, pero no todos los números que contienen `123`.

3. **Caso borde, sin dígitos:**
   - En el filtro de facturas, buscar `+` o `N/A` en el teléfono.
   - **Verificar:** Ningún resultado, en vez de todos los que tienen teléfono.

## 📝 Notas de Despliegue

No hay migraciones. Los buscadores pueden encontrar más que antes, que es el objetivo. En la instalación de la diaria, esto va antes del cambio de `utopia-crm-ladiaria`, que importa `phone_search_q`.

## 📚 Detalles Técnicos

Medido en una copia local con 640.959 contactos, mediana de 8 números reales escritos con el 0:

| Buscador | Antes | Después |
| --- | --- | --- |
| Contactos | 183 ms | 198 ms |
| Facturas | 90 ms | 48 ms |
| Tareas programadas | 206 ms | 193 ms |
| Sólo teléfonos, tres campos | 38 ms | 56 ms |

`contains` reemplaza a `icontains`, que aplicaba `UPPER` a dígitos sin necesidad. Por eso facturas se hizo más rápido aunque busque dos formas.

El test de contactos crea la extensión `unaccent`: el buscador la necesita, pero ninguna migración la crea (`INSTALL.md` dice crearla a mano), y por eso este buscador no tenía tests.

## 🎓 Decisiones de Diseño

- **Sin las búsquedas internas:** `identify_phone` y otras parecidas usan `Contact.objects.get`, que falla con más de una coincidencia. Encontrar más podría romperlas.
- **Los mismos campos que tenía cada buscador:** facturas y tareas programadas no buscan en `work_phone`, y esto no lo agrega.
- **Sin normalizar los números guardados en la consulta:** limpiar cada número en la base encontraría `06220308` en `062 2 0308`, pero recorriendo toda la tabla en cada búsqueda.

---

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl106-buscar-telefono
- **Tipo:** Corrección de errores
- **Módulos afectados:** core, support, invoicing, tests
