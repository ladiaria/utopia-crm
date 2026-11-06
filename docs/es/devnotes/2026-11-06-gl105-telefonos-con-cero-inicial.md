# Buscar contactos existentes encuentra los teléfonos escritos con el 0 inicial

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#105
- **Tipo:** Corrección de errores
- **Componente:** Support
- **Impacto:** Gestión de campañas

## 🎯 Resumen

La búsqueda por teléfono mira si los dígitos del CSV están dentro del número guardado. Los números se guardan con el código de país, así que `099123456` no es parte de `+59899123456`: el contacto aparecía en «No hay coincidencias» y parecía nuevo. Ahora la búsqueda prueba el número con y sin sus ceros iniciales.

## ✨ Cambios

### 1. La búsqueda prueba las dos formas

**Archivo:** `support/views/contacts.py`

```python
without_leading_zeros = phone_without_plus.lstrip('0')
if without_leading_zeros != phone_without_plus:
    phone_query |= Q(phone__icontains=without_leading_zeros)
    mobile_query |= Q(mobile__icontains=without_leading_zeros)
```

Conserva la forma con el 0 porque unos 2.000 números viejos están guardados así. Las etiquetas «Teléfono» y «Celular» usan las mismas condiciones. También funciona con prefijo internacional: `00598 99 123 456` encuentra el número.

### 2. Los ceros iniciales no cuentan para el mínimo

**Archivo:** `support/views/contacts.py`

```python
if len(re.sub(r'\D', '', value).lstrip('0')) < self.min_phone_digits:
```

Sin esto, `0000000` tiene 7 dígitos pero queda como una búsqueda vacía, que coincide con todos los contactos. `0123456` tampoco se busca, porque buscaría `123456`.

### 3. Las instrucciones

**Archivos:** `support/templates/check_for_existing_contacts.html`, `locale/es/LC_MESSAGES/django.po`

Ya no piden sacar el 0. El mínimo ahora aclara que los ceros iniciales no cuentan, y el aviso sobre cómo están escritos los teléfonos sale de «No hay coincidencias».

## 📁 Archivos Modificados

- **`support/views/contacts.py`** — La búsqueda y el mínimo
- **`support/templates/check_for_existing_contacts.html`** — Las instrucciones
- **`locale/es/LC_MESSAGES/django.po`** — Traducciones
- **`tests/test_check_existing_contacts.py`** — El 0 inicial en `phone` y `mobile`, los números guardados con el 0, el prefijo internacional y el mínimo

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - Subir un CSV con una columna `phone` y un número que exista, escrito como `099…`.
   - **Verificar:** El contacto está en los resultados, con la etiqueta que corresponde.

2. **Caso borde, sólo ceros:**
   - Subir un CSV con `0000000` y `0123456`.
   - **Verificar:** La respuesta es inmediata y los dos están en «Teléfonos sin buscar».

## 📝 Notas de Despliegue

No hay migraciones. Pueden aparecer más coincidencias que antes, que es justamente el objetivo del cambio. Mergear reinicia la aplicación.

## 📚 Detalles Técnicos

Medido en una copia local con 640.959 contactos y 80 celulares reales: todos se encontraron escritos con el 0, con una mediana de 1 coincidencia por fila y un máximo de 3. Una fila con el 0 tarda unos 170 ms, y una sin él unos 105 ms, porque busca dos veces. Las filas que no empiezan con 0 no cambian. Agrupar las búsquedas sigue pendiente en it/utopia-crm-ladiaria#105.

---

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl105-telefono-cero-inicial
- **Tipo:** Corrección de errores
- **Módulos afectados:** support, locale, tests
