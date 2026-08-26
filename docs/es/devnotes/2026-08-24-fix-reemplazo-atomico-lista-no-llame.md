# Corrección: Reemplazo Atómico de la Lista de "No Llame"

- **Fecha:** 2026-08-24
- **Autor:** Tanya Tree + Claude Opus 5
- **Ticket:** fix/upload_do_not_call_numbers (sin ticket)
- **Tipo:** Corrección (+ Rendimiento, Seguridad)
- **Componente:** Support — Gestión de Campañas, Modelos Core (DoNotCallNumber)
- **Impacto:** Integridad de Datos, Rendimiento, Control de Acceso, Experiencia de Usuario

## 🎯 Resumen

La subida de la lista de "no llame" (`/support/upload_do_not_call_numbers/`) empezó a fallar con
`IntegrityError: duplicate key value violates unique constraint "core_donotcallnumber_pkey"` sobre el
**primer** número del archivo. El CSV subido resultó estar limpio (512.734 filas, todas de 8 dígitos,
cero duplicados, cero vacías) y el borrado funcionaba correctamente al reproducirlo en un shell. La
causa era estructural: `delete_all_numbers()` y `upload_new_numbers()` corrían en **dos transacciones
separadas**, así que los varios segundos entre una y otra eran una ventana en la que una segunda
subida (un doble clic en el botón, un reenvío del navegador) podía no borrar nada — la primera ya
había confirmado su borrado — e insertar los mismos números que la primera todavía estaba insertando.
La que confirmaba segunda se llevaba el error de clave duplicada.

Esa misma brecha escondía una falla peor: como el borrado se confirmaba por su cuenta, **cualquier**
error durante la inserción dejaba la tabla vacía, con lo que en silencio todos los contactos volvían a
ser llamables.

La corrección convierte el reemplazo en una única operación atómica, endurece el parseo para que una
fila malformada no aborte la carga entera, restringe la herramienta a administradores (destruye la
lista completa) y reescribe un template que todavía arrastraba textos copiados de la pantalla de
información complementaria de direcciones.

## ✨ Cambios

### 1. Borrado e inserción en una sola transacción

**Archivo:** `core/models.py`

Un nuevo `DoNotCallNumber.replace_all_numbers()` envuelve ambos pasos en un único bloque
`transaction.atomic()`. O la lista nueva queda completa, o la anterior sobrevive intacta:

```python
numbers, discarded = DoNotCallNumber.clean_numbers(numbers_list)
if not numbers:
    return 0, discarded
with transaction.atomic():
    DoNotCallNumber.delete_all_numbers()
    DoNotCallNumber._bulk_create_numbers(numbers, batch_size=batch_size)
return len(numbers), discarded
```

El retorno temprano importa tanto como la transacción: un archivo del que no sale ningún número válido
se trata como un archivo roto y no se toca nada. Reemplazar la lista por nada nunca es el resultado
buscado.

`delete_all_numbers()` y `upload_new_numbers()` conservan su significado original (solo borrar / solo
insertar), así que cualquier llamador externo de la app base sigue funcionando.

### 2. TRUNCATE en lugar de DELETE, que además serializa subidas simultáneas

**Archivo:** `core/models.py`

La lista tiene cientos de miles de filas. En PostgreSQL la tabla ahora se vacía con `TRUNCATE`, que es
mucho más rápido que un `DELETE` y —lo que importa acá— toma un lock `ACCESS EXCLUSIVE` que se
mantiene hasta el commit. Dos subidas simultáneas ahora hacen cola una detrás de la otra en vez de
entremezclarse, que es exactamente la carrera que producía el error de clave duplicada:

```python
if connection.vendor == "postgresql":
    with connection.cursor() as cursor:
        cursor.execute('TRUNCATE TABLE "{}"'.format(DoNotCallNumber._meta.db_table))
else:
    DoNotCallNumber.objects.all().delete()
```

El nombre de la tabla sale del `_meta` del modelo, nunca de entrada del usuario. La rama no-PostgreSQL
mantiene la app base funcionando sobre otros motores.

### 3. Las filas que abortaban el insert completo ahora se descartan

**Archivo:** `core/models.py`

`clean_numbers()` normaliza las filas antes de insertar nada. Filas vacías, valores en blanco, valores
repetidos y valores más largos que la columna se descartan y se cuentan, dado que uno solo de ellos
abortaba el `bulk_create` entero:

```python
max_length = DoNotCallNumber._meta.get_field("number").max_length
numbers, discarded = {}, 0
for row in rows:
    value = row[0].strip() if row else ""
    if not value or len(value) > max_length:
        discarded += 1
        continue
    # A dict keeps insertion order and removes duplicates in a single pass.
    numbers[value] = None
return list(numbers), discarded
```

El código anterior hacía `DoNotCallNumber(number=number[0])` sin ninguna guarda, así que una fila
vacía lanzaba `IndexError` y un número repetido lanzaba `IntegrityError`.

### 4. Inserción por lotes, parseo sin materializar el archivo

**Archivo:** `core/models.py`, `support/views/all_views.py`

`bulk_create` ahora corre con `batch_size=5000` en vez de armar un único INSERT de medio millón de
filas, y la vista parsea con `io.StringIO` + `itertools.islice` en vez de `splitlines()`, que armaba
una lista de 512k strings antes de que el lector CSV siquiera arrancara. Medido contra el archivo
real: **7,0 s → 4,7 s**, con un consumo de memoria sustancialmente menor.

`islice` además reemplaza las dos llamadas peladas a `next(numbers)`, que lanzaban `StopIteration` (un
500) con un archivo de menos de dos filas.

### 5. Restringida a administradores

**Archivo:** `support/views/all_views.py`, `support/templates/campaign_management_menu.html`, `templates/components/sidebar_items/_campaign_management.html`

La vista destruye la lista entera, así que `@staff_member_required` ya no alcanza. Ahora usa
`@user_passes_test(user_is_admin)`, siguiendo el patrón que ya usan `BulkReassignIssueStatusView` y
`BulkDeleteCampaignStatusView`:

```python
def user_is_admin(user):
    return user.is_superuser or user.groups.filter(name="Admins").exists()
```

La tarjeta del menú de Gestión de Campañas y la entrada del sidebar quedan envueltas en
`{% if request.user|in_group_exclusive:"Admins" %}` para que quien no pueda ejecutarla no vea el
enlace.

### 6. Template reescrito, con devolución al operador

**Archivo:** `support/templates/upload_do_not_call_numbers.html`

El título de la tarjeta del template decía *"Upload address complementary information"* y su `div`
contenedor todavía era `id="address_complementary_information"` — restos de un copy-paste. Nada en la
pantalla decía que la subida **reemplaza la lista entera**. Ahora muestra un callout de advertencia
que lo dice explícitamente, la cantidad de números guardados en ese momento, un campo `header_rows`
(por defecto 2, ya que el archivo que publica el organismo trae dos filas de encabezado) y un botón
Cancelar que vuelve a Gestión de Campañas.

La vista informa el resultado mediante `messages` — cuántos números se cargaron, cuántas filas se
ignoraron, o el error con la lista anterior conservada — en vez de redirigir siempre a `/` con un
mensaje de éxito genérico. El archivo se decodifica como UTF-8 con fallback a latin-1, el mismo patrón
que ya usa `tag_contacts`.

## 📁 Archivos Modificados

- **`core/models.py`** — `DoNotCallNumber`: `replace_all_numbers()`, `clean_numbers()`, `_bulk_create_numbers()`, `delete_all_numbers()` basado en TRUNCATE, `upload_new_numbers()` por lotes
- **`support/views/all_views.py`** — `upload_do_not_call_numbers` reescrita; se agregó el helper `user_is_admin`
- **`support/templates/upload_do_not_call_numbers.html`** — reescritura completa (textos copiados incorrectos, sin explicación del comportamiento destructivo)
- **`support/templates/campaign_management_menu.html`** — tarjeta oculta para quien no sea admin, descripción actualizada
- **`templates/components/sidebar_items/_campaign_management.html`** — entrada del sidebar oculta para quien no sea admin

## 📁 Archivos Creados

- **`tests/test_upload_do_not_call_numbers.py`** — 10 tests que cubren permisos, reemplazo, números repetidos, números ya guardados, filas vacías/demasiado largas, archivos vacíos, codificación latin-1 y la opción de filas de encabezado

## 📚 Detalles Técnicos

**Por qué el error apuntaba a la primera fila.** Postgres reporta la primera clave en conflicto que
encuentra. Con el borrado ya confirmado por la petición A, la petición B no borraba nada y empezaba a
insertar desde el principio del mismo archivo, así que la colisión aparecía en la fila 1. Por eso el
error parecía "el borrado no funciona" cuando en realidad el borrado funcionaba perfectamente.

**Por qué `TRUNCATE` es seguro dentro de una transacción.** A diferencia de MySQL, el `TRUNCATE` de
PostgreSQL es completamente transaccional y se revierte junto con el bloque que lo contiene. La suite
de tests depende de esto: cada test corre dentro de la transacción de `TestCase` y los datos se
restauran después.

**Compatibilidad hacia atrás.** `delete_all_numbers()` y `upload_new_numbers()` conservan sus nombres
y su semántica original. `upload_new_numbers()` sumó un argumento opcional `batch_size` y ahora
devuelve una tupla `(loaded, discarded)` donde antes devolvía `None`; dentro de la suite se llama
únicamente desde esta vista.

## 🧪 Pruebas Manuales

1. **Caso exitoso — reemplazar la lista:**
   - Ingresar como superusuario o miembro del grupo `Admins`
   - Ir a Gestión de Campañas → Subir lista de no llame
   - Confirmar que la pantalla muestra cuántos números hay guardados
   - Subir el CSV del organismo dejando "Filas de encabezado a saltear" en 2
   - **Verificar:** redirige a Gestión de Campañas con un mensaje que indica cuántos números se cargaron, y al reabrir la pantalla de subida aparece esa misma cantidad como guardada

2. **Caso borde — un archivo del que no sale ningún número válido:**
   - Subir un archivo que contenga solo sus dos filas de encabezado
   - **Verificar:** un mensaje de error indica que no se encontraron números válidos y que se conservó la lista anterior; la cantidad guardada en la pantalla no cambia

3. **Caso borde — números repetidos:**
   - Subir un archivo donde un número aparezca dos veces
   - **Verificar:** la subida tiene éxito, el número queda guardado una sola vez y una advertencia informa las filas ignoradas

4. **Control de acceso:**
   - Ingresar como usuario staff que **no** esté en `Admins`
   - **Verificar:** la tarjeta "Subir lista de no llame" y la entrada del sidebar no son visibles, y navegar directamente a `/support/upload_do_not_call_numbers/` redirige a la pantalla de login

5. **Regresión — las marcas de no llamar siguen resolviendo:**
   - Después de una subida exitosa, abrir un contacto cuyo teléfono esté en la lista
   - **Verificar:** la ficha del contacto y la consola de vendedores siguen marcando el teléfono como "No llamar"

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos
- No se requieren cambios de configuración
- No se requieren comandos post-despliegue
- Quienes necesiten esta herramienta deben pertenecer al grupo `Admins` (o ser superusuarios). Ser
  staff ya no alcanza — conviene confirmarlo con quien hace la subida antes de desplegar
- La subida es una petición larga (aproximadamente 5 s de trabajo de base de datos más la
  transferencia del archivo, para un archivo de 5 MB). Queda holgadamente dentro de los límites
  habituales de los proxies, pero conviene tenerlo presente si el archivo crece

## 🚀 Mejoras Futuras

- Usar `COPY` de PostgreSQL en lugar de `bulk_create` si la lista crece al punto de que 5 s sean un problema
- Registrar quién reemplazó la lista y cuándo (un `LogEntry`, como ya hace la vista de reasignación masiva)
- Mover la subida a un management command o a un job en segundo plano si el archivo llegara a ser lo bastante grande como para arriesgar un timeout de la petición

---

- **Fecha:** 2026-08-24
- **Autor:** Tanya Tree + Claude Opus 5
- **Branch:** fix/upload_do_not_call_numbers
- **Tipo de cambio:** Corrección (+ Rendimiento, Seguridad)
- **Módulos afectados:** Core, Support
