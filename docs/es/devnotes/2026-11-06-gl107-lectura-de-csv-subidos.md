# Una sola forma de leer los CSV que sube la gente

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#107
- **Tipo:** Corrección de errores
- **Componente:** Core, Support, Logistics
- **Impacto:** Integridad de datos, Experiencia de usuario

## 🎯 Resumen

Cada pantalla que recibe un CSV lo decodificaba a su manera. Lo que guarda Excel depende de la opción y del idioma: un BOM con «CSV UTF-8», cp1252 con «CSV» común, y punto y coma en español. Según la pantalla, eso terminaba en un error 500 o, peor, en datos mal cargados sin ningún error. Ahora todas las pantallas de este repo leen con las mismas funciones de `core/utils.py`.

## ✨ Cambios

### 1. Las funciones de lectura

**Archivo:** `core/utils.py`

- **`uploaded_csv_content`** decodifica UTF-8 con o sin BOM, después cp1252, con latin-1 como último recurso, y detecta el delimitador.
- **`read_uploaded_csv`** lee por nombre de columna, como ya hacía. Una fila corta recibe cadenas vacías, lo que le sobra a una fila larga va a `extra_columns`, y se sacan los espacios alrededor de los nombres de columna.
- **`read_uploaded_csv_rows`** es nueva, para los archivos que se leen por posición.

cp1252 reemplaza a latin-1 como primera alternativa: en latin-1, los `’`, `–` y `€` de Excel se vuelven caracteres de control.

### 2. Qué hacía mal cada pantalla

**Archivos:** `support/views/all_views.py`, `support/views/campaign_management.py`, `support/views/contacts.py`, `logistics/views.py`

| Pantalla | Con un archivo de Excel, antes |
| --- | --- |
| Lista de no llamar | Guardaba `﻿099123456` o `099123456;Ana`, que no coinciden con nadie |
| Etiquetar contactos | Salteaba la primera fila con BOM, no agregaba nada con punto y coma, y una fila sin etiqueta daba error 500 |
| Borrado masivo de estados de campaña | Error 500 con «CSV» común, y «no se encontró la columna» con BOM |
| Importar contactos | No importaba nada con punto y coma ni con «CSV» común |
| Etiquetas desde CSV | Error 500 con «CSV» común, y «cantidad de columnas incorrecta» con punto y coma |
| Imprimir etiquetas del día | Error 500 con cualquier archivo: pasaba filas enteras como ids |
| Imprimir etiquetas | Error 500 con encabezado o con BOM |

### 3. Importar contactos: una fila larga ya no corre los datos

**Archivo:** `support/views/contacts.py`

Con una fila más larga que el encabezado, pandas tomaba la primera columna como índice: el nombre pasaba al apellido, sin ningún error. `index_col=False` lo evita.

## 📁 Archivos Modificados

- **`core/utils.py`** — Las funciones de lectura
- **`support/views/all_views.py`** — Lista de no llamar y etiquetar contactos
- **`support/views/campaign_management.py`** — Borrado masivo
- **`support/views/contacts.py`** — Importar contactos
- **`logistics/views.py`** — Las tres pantallas de etiquetas
- **`locale/es/LC_MESSAGES/django.po`** — El mensaje de las filas sin etiqueta
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`tests/test_read_uploaded_csv.py`** — Codificaciones, delimitadores, y archivos cortos, largos y vacíos
- **`tests/test_csv_uploads.py`** — Cada pantalla con lo que guarda Excel

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - En una planilla en español, guardar como «CSV» una lista de ids de contacto y etiquetas, con un acento en una etiqueta, y subirla a Etiquetar contactos.
   - **Verificar:** Se etiquetan todas las filas, también la primera, y el acento se lee bien.

2. **Caso borde, fila sin etiqueta:**
   - Subir el mismo archivo con una fila que sólo tenga el id.
   - **Verificar:** Se etiqueta el resto, y un mensaje dice cuántas filas se saltearon.

3. **Caso borde, la lista de no llamar:**
   - Subir una lista guardada como «CSV UTF-8», con `0` filas de encabezado.
   - **Verificar:** En el admin, el primer número no tiene caracteres raros.

## 📝 Notas de Despliegue

No hay migraciones. Los archivos que funcionaban siguen funcionando igual. Esto va antes del cambio de `utopia-crm-ladiaria`, que usa `read_uploaded_csv_rows`.

## 📚 Detalles Técnicos

En una copia local de la lista de no llamar, los 522.809 números están limpios: el problema no había pasado con los archivos subidos hasta ahora.

La detección del delimitador se prueba con los casos que más la pueden confundir: comas dentro de los valores de un archivo con punto y coma, comas entre comillas, un punto y coma entre comillas en un archivo con comas, una sola columna y un archivo vacío.

## 🎓 Decisiones de Diseño

- **Los archivos de formato fijo quedan afuera:** los de bancos y procesadoras de tarjetas tienen una codificación y un delimitador que define quien los genera.
- **Los tests de imprimir etiquetas simulan `Canvas`:** sin nada para dibujar, el PDF falla por sí mismo en `flush`, y eso no tiene que ver con leer el archivo.

---

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl107-lectura-csv
- **Tipo:** Corrección de errores
- **Módulos afectados:** core, support, logistics, locale, tests
