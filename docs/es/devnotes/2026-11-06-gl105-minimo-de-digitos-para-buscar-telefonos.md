# Buscar contactos existentes: mínimo de 7 dígitos para buscar un teléfono, e instrucciones que coinciden con la pantalla

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#105
- **Tipo:** Corrección de errores
- **Componente:** Support
- **Impacto:** Gestión de campañas

## 🎯 Resumen

La búsqueda por teléfono saca todo lo que no sea dígito y busca con `icontains`. Un valor sin dígitos (`N/A`, `-`) quedaba como una búsqueda vacía, que coincidía con todos los contactos y los cargaba en memoria, con sus suscripciones. Medido en una copia local con 640.959 contactos: `N/A` coincidía con todos y `099` con 3.985.

Un teléfono con menos de 7 dígitos ya no se busca. Va a su propia tabla, porque las instrucciones presentan «No hay coincidencias» como candidatos para importar. Las instrucciones también decían cosas que la pantalla no hace, así que se corrigen.

## ✨ Cambios

### 1. Mínimo de dígitos para buscar un teléfono

**Archivo:** `support/views/contacts.py`

```python
if len(re.sub(r'\D', '', value)) < self.min_phone_digits:
    not_searched_phones.append({'value': value, 'row_number': row_number + 1})
    continue
```

`min_phone_digits` es un atributo de la clase, con valor 7. Los símbolos no cuentan, así que `+99-12-34` no se busca. Una celda de teléfono vacía va a la misma lista, en vez de aparecer como `N/A` en «No hay coincidencias». El chequeo por email no cambia.

### 2. Una tabla para lo que no se buscó

**Archivo:** `support/templates/check_for_existing_contacts.html`

«Teléfonos sin buscar» aparece arriba de los resultados, con la fila del CSV, el valor y su propia exportación.

### 3. El «CSV UTF-8» de Excel

**Archivo:** `support/views/contacts.py`

Excel empieza estos archivos con un BOM, que quedaba como parte del nombre de la primera columna: no encontraba `email` y todas las filas aparecían como `N/A`. Ahora el archivo se decodifica con `utf-8-sig`. Las instrucciones recomiendan este formato, así que sin este cambio habrían mandado a la gente directo a la falla.

### 4. Las instrucciones

**Archivos:** `support/templates/check_for_existing_contacts.html`, `locale/es/LC_MESSAGES/django.po`

| Tema | Antes | Ahora |
| --- | --- | --- |
| Formato del teléfono | Nada | Con código de país o sin el 0 inicial: `099123456` en general no se encuentra, porque el 97,5 % de los teléfonos está guardado como `+598…` |
| Números parciales | Nada | El número del CSV puede ser parte del guardado, así que una fila puede encontrar varios contactos |
| Mínimo | Nada | Con menos de 7 dígitos no se busca |
| «No hay coincidencias» | «No existen en la base de datos» | «No se encontraron», y revisar cómo están escritos los teléfonos |
| Pro Tip | Subir a la importación el export de «No hay coincidencias» | No se puede subir tal cual: la importación tiene su propia plantilla, con otras columnas |
| Nombre de la columna | «Debe contener una columna 'email'» | Exactamente `email`, en minúsculas: `Email` no se reconoce |
| Codificación | Nada | Guardar en UTF-8 |

Los dos títulos del panel «Qué esperar» pierden el color, porque el verde casi no se leía sobre el azul. En español se corrigen erratas («bse», «enconttradas», «entcontradas»), y los textos que cambian van en voseo.

## 📁 Archivos Creados

- **`tests/test_check_existing_contacts.py`** — El mínimo, las listas, el 0 inicial y el BOM

## 📁 Archivos Modificados

- **`support/views/contacts.py`** — El mínimo, la lista y la decodificación
- **`support/templates/check_for_existing_contacts.html`** — La tabla y las instrucciones
- **`locale/es/LC_MESSAGES/django.po`** — Traducciones

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - Subir un CSV con una columna `phone` y un número que exista, escrito como `+598…`.
   - **Verificar:** El contacto está en los resultados, y no aparece la tabla «Teléfonos sin buscar».

2. **Caso borde, valores que no se pueden buscar:**
   - Subir un CSV con `N/A`, `-` y `099`.
   - **Verificar:** La respuesta es inmediata, los tres están en «Teléfonos sin buscar» y ninguno en «No hay coincidencias».

3. **Caso borde, Excel:**
   - Guardar desde Excel un CSV con una columna `email` como «CSV UTF-8» y subirlo.
   - **Verificar:** Los emails se buscan, y las filas no aparecen como `N/A`.

## 📝 Notas de Despliegue

No hay migraciones. Mergear reinicia la aplicación, y quien esté esperando un resultado en esa pantalla lo pierde. Cambia `django.po`, así que el server compila las traducciones.

## 🚀 Mejoras Futuras

Lo demás está en it/utopia-crm-ladiaria#105: agrupar las búsquedas para evitar las consultas por fila, y decidir qué hacer con las coincidencias parciales.

## 🎓 Decisiones de Diseño

- **Una tabla aparte, y no «No hay coincidencias»:** esa lista es la que la gente lleva a la importación, y un valor que no se buscó no dice nada sobre si el contacto existe.
- **El 0 inicial se documenta, no se cambia:** encontrar esos números cambia lo que devuelve la búsqueda. Es una decisión aparte.

---

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl105-telefonos-minimo-digitos
- **Tipo:** Corrección de errores
- **Módulos afectados:** support, locale, tests
