# Imprimir etiquetas ya no falla cuando no hay nada para imprimir

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#110
- **Tipo:** Corrección de errores
- **Componente:** Logistics
- **Impacto:** Experiencia de usuario

## 🎯 Resumen

Un día sin etiquetas daba un error 500 (`IndexError: pop from empty list`) en todas las pantallas de etiquetas. `SheetLayout.flush` restaura un estado de reportlab que recién se guarda al pedir la primera etiqueta, así que sin etiquetas no había nada para restaurar. Ahora el PDF sale con una página que dice que no hay nada para imprimir.

## ✨ Cambios

### 1. `flush` sabe si hubo etiquetas

**Archivo:** `logistics/labels.py`

`iterator` marca `has_labels` al pedir la primera etiqueta. Sin etiquetas, `flush` escribe el mensaje en vez de restaurar el estado. Como todas las pantallas de etiquetas pasan por `flush`, no hubo que cambiar ninguna, tampoco las de un paquete de customización.

## 📁 Archivos Modificados

- **`logistics/labels.py`** — El arreglo
- **`locale/es/LC_MESSAGES/django.po`** — El mensaje
- **`tests/test_csv_uploads.py`** — Sus tests de imprimir etiquetas ya no necesitan simular `Canvas`
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`tests/test_labels_without_data.py`** — Los tres formatos de hoja, las pantallas sin etiquetas, y una hoja con etiquetas

## 🧪 Pruebas Manuales

1. **Caso exitoso:**
   - Imprimir las etiquetas de un día que las tenga.
   - **Verificar:** Salen como siempre, sin una página de más con el mensaje.

2. **Caso borde, sin etiquetas:**
   - Subir a «Etiquetas desde CSV» un archivo con sólo el encabezado.
   - **Verificar:** El PDF abre, con «No hay etiquetas para imprimir».

## 📝 Notas de Despliegue

No hay migraciones.

## 🎓 Decisiones de Diseño

- **Una página con el mensaje, no un aviso en pantalla:** arregla todas las pantallas desde un solo lugar. Un aviso en pantalla obligaría a cambiar cada vista que imprime etiquetas. En un rollo, el mensaje ocupa una etiqueta.

---

- **Fecha:** 2026-11-06
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl110-etiquetas-sin-datos
- **Tipo:** Corrección de errores
- **Módulos afectados:** logistics, locale, tests
