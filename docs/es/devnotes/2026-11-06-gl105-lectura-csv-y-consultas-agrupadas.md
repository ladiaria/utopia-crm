# Buscar contactos existentes: cualquier CSV de una planilla, y los emails en una consulta

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#105
- **Tipo:** Corrección de errores, Rendimiento
- **Componente:** Core, Support
- **Impacto:** Gestión de campañas

## 🎯 Resumen

La pantalla daba un error 500 con un CSV que no estaba en UTF-8 y con una fila con menos columnas que el encabezado, y hacía 3 consultas por fila. Un archivo de 2.000 emails tardaba casi 3 minutos mientras la persona esperaba. Ahora lee esos archivos, busca todos los emails en una consulta, y cada fila de teléfono hace una consulta en vez de tres.

## ✨ Cambios

### 1. Una función para leer los CSV que sube la gente

**Archivo:** `core/utils.py`

`read_uploaded_csv` decodifica como UTF-8, con o sin BOM, y si no puede usa latin-1, que es como Excel guarda un «CSV» común. Detecta el delimitador, y una fila con menos columnas recibe cadenas vacías en vez de `None`. Devuelve el `DictReader` y el delimitador. Por ahora sólo la usa esta pantalla.

### 2. Los emails en una consulta

**Archivo:** `support/views/contacts.py`

`find_matching_contacts_by_emails` los busca todos con `Lower` e `IN`, y devuelve un diccionario por email en minúsculas. Sigue sin distinguir mayúsculas, y los resultados mantienen el orden de las filas.

### 3. Lo que muestra la tabla viene en la misma consulta

**Archivo:** `support/views/contacts.py`

`with_results_data` anota `has_active_subscription` e `is_in_active_campaign` con `Exists`. Eso reemplaza el prefetch de suscripciones, el `Count` y el prefetch de `contactcampaignstatus_set`, que no usaba nadie. También salen las claves `count` y `email_matches`, que el template no usaba, y el `print` de progreso.

## 📁 Archivos Modificados

- **`core/utils.py`** — `read_uploaded_csv`
- **`support/views/contacts.py`** — La búsqueda agrupada y las anotaciones
- **`tests/test_check_existing_contacts.py`** — Latin-1, filas cortas, orden de las filas, los datos de la tabla y la cantidad de consultas
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - Subir un CSV de 2.000 emails.
   - **Verificar:** Responde en alrededor de un segundo, con los mismos resultados.

2. **Caso borde, latin-1:**
   - Guardar en Excel un archivo con un acento como «CSV» común y subirlo.
   - **Verificar:** Responde normalmente en vez de un error 500.

3. **Caso borde, fila corta:**
   - Subir un archivo con una fila con menos columnas que el encabezado.
   - **Verificar:** La fila aparece sin coincidencia, o en «Teléfonos sin buscar», en vez de un error 500.

## 📝 Notas de Despliegue

No hay migraciones. No cambia lo que encuentra la pantalla. Va después del PR de los buscadores de teléfono (it/utopia-crm-ladiaria#106), sobre el que está armado.

## 📚 Detalles Técnicos

Medido por la pantalla en una copia local con 640.959 contactos:

| Archivo | Antes | Después | Consultas antes | Consultas después |
| --- | --- | --- | --- | --- |
| 300 emails | 26,3 s | 0,75 s | 907 | 8 |
| 2.000 emails | 166,7 s | 0,55 s | 6.007 | 8 |
| 300 teléfonos | 17,4 s | 16,2 s | 907 | 307 |

Los teléfonos casi no cambian, porque casi todo el tiempo está en buscar los dígitos dentro de cada número en toda la tabla.

## 🚀 Mejoras Futuras

- **Las demás subidas de CSV:** podrían usar `read_uploaded_csv` (it/utopia-crm-ladiaria#107). Los formatos fijos de bancos y procesadoras de tarjetas deberían quedar como están.

## 🎓 Decisiones de Diseño

- **Sin índice para los teléfonos:** un índice `pg_trgm` en `phone`, `mobile` y `work_phone` bajó 300 teléfonos de 16,2 s a 3,2 s en una prueba que se revirtió, y ocupa unos 22 MB. Se descartó: con unos 54 ms por fila esta pantalla es aceptable, los buscadores andan bien, y no justifica una extensión y una migración nuevas. Si alguien sube seguido archivos de miles de teléfonos, estos números son el punto de partida. En Django 4.2 hay que escribirlo con `fields` y `opclasses`: `OpClass` sobre una columna genera SQL inválido.
- **Tampoco una expresión regular:** una sola consulta con todos los números cuesta más o menos lo mismo por número, con o sin el índice.

---

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl105-csv-consultas-agrupadas
- **Tipo:** Corrección de errores, Rendimiento
- **Módulos afectados:** core, support, tests
