# Descarga CSV de Estadísticas de Campaña

**Fecha:** 2026-03-10
**Autor:** Trifero + programador AI en par
**Ticket:** t1052
**Tipo:** Funcionalidad
**Componente:** Gestión de Campañas, Estadísticas
**Impacto:** Flujo de trabajo de Managers, Análisis de Campañas, Exportación de Datos

## 🎯 Resumen

Se agregó un botón de descarga CSV a la vista `CampaignStatisticsDetailView` para que los managers puedan descargar datos por contacto de una campaña. La exportación respeta todos los filtros activos (vendedor, estado, rangos de fechas) e incluye 17 columnas con información de contacto, resolución de campaña, asignación de vendedor, cantidad de actividades y datos de suscripción (fecha de inicio y productos vendidos). Las consultas están optimizadas para evitar problemas N+1 usando `select_related`, anotación `Count` y precarga masiva de suscripciones.

## ✨ Cambios

### 1. Método de Exportación CSV en CampaignStatisticsDetailView

**Archivo:** `support/views/all_views.py`

Se agregó un override de `get()` para interceptar `?export=csv` y redirigir a un nuevo método `export_csv()`. El método:

- Aplica el mismo `ContactCampaignStatusFilter` que la vista de la página
- Usa `select_related('contact', 'seller', 'last_console_action')` para evitar lookups de FK en el loop
- Anota `activity_count` via `Count` con filtro en la campaña actual
- Construye un diccionario `contact_id → {start_date, products}` desde `Subscription` + `SubscriptionProduct` en dos consultas masivas
- Procesa filas con `iterator(chunk_size=1000)` para eficiencia de memoria

```python
def get(self, request, *args, **kwargs):
    if request.GET.get("export") == "csv":
        return self.export_csv()
    return super().get(request, *args, **kwargs)
```

Columnas del CSV (17 en total):

| Columna | Origen |
| --- | --- |
| ID Contacto, Nombre, Email, Teléfono, Celular | Modelo `Contact` |
| Estado | `ContactCampaignStatus.get_status()` |
| Resolución de campaña | `ContactCampaignStatus.get_campaign_resolution()` |
| Razón de resolución | `ContactCampaignStatus.get_resolution_reason()` |
| Vendedor | `ContactCampaignStatus.seller.name` |
| Fecha asignación, Última acción, Fecha creación | Campos de fecha de `ContactCampaignStatus` |
| Veces contactado | `ContactCampaignStatus.times_contacted` |
| Cantidad de actividades | Anotación `Count` de actividades para esta campaña |
| Última acción de consola | `SellerConsoleAction.name` |
| Fecha inicio suscripción | `Subscription.start_date` (vinculada via FK campaign) |
| Productos vendidos | Nombres de `SubscriptionProduct` separados por coma |

### 2. Botón de Exportación en el Template

**Archivo:** `support/templates/campaign_statistics_detail.html`

Se agregó un botón verde "Export CSV" dentro del `<form>` de filtros existente. Al usar `<button type="submit" name="export" value="csv">`, automáticamente incluye todos los parámetros de filtro activos — sin necesidad de URLs adicionales ni JavaScript.

```html
<button type="submit" name="export" value="csv" class="btn bg-gradient-success">
  <i class="fas fa-file-csv"></i> {% trans "Export CSV" %}
</button>
```

## 📁 Archivos Modificados

- **`support/views/all_views.py`** — Se agregaron métodos `get()` y `export_csv()` a `CampaignStatisticsDetailView`
- **`support/templates/campaign_statistics_detail.html`** — Se agregó botón "Export CSV" junto a las acciones de filtro

## 📚 Detalles Técnicos

### Cómo se Relacionan las Suscripciones con las Campañas

El modelo `Subscription` tiene un FK `campaign` hacia `Campaign`. Cuando un vendedor realiza una venta exitosa a través de la consola de vendedor, la suscripción se vincula a la campaña mediante `ContactCampaignStatus.handle_direct_sale()` que establece `subscription.campaign = self.campaign`. Esto permite consultar todas las suscripciones vendidas a través de una campaña y sus productos.

### Estrategia de Optimización de Consultas

La exportación ejecuta un número fijo de consultas sin importar el tamaño del dataset:

1. **Consulta principal:** `ContactCampaignStatus` filtrado con `select_related` + anotación `Count`
2. **Consulta de suscripciones:** Todos los objetos `Subscription` para esta campaña con `SubscriptionProduct` → `Product` precargados
3. **Loop:** Cero consultas adicionales — todos los datos accedidos desde campos precargados/anotados

## 🧪 Pruebas Manuales

1. **Caso exitoso — exportar sin filtros:**
   - Navegar a Estadísticas de Campaña para una campaña activa
   - Hacer clic en "Export CSV" sin aplicar filtros
   - **Verificar:** Se descarga un CSV con nombre `campaign_{id}_{fecha}.csv`, contiene todos los contactos de la campaña con datos correctos en las 17 columnas

2. **Exportar con filtros aplicados:**
   - Seleccionar un vendedor del dropdown y establecer un rango de fechas
   - Hacer clic en "Aplicar filtros" para ver resultados filtrados
   - Hacer clic en "Export CSV"
   - **Verificar:** El CSV contiene solo el subconjunto filtrado de contactos, coincidiendo con la cantidad mostrada en la página

3. **Caso borde — campaña sin suscripciones:**
   - Exportar CSV para una campaña donde no se realizaron ventas
   - **Verificar:** El CSV se descarga correctamente; las columnas "Fecha inicio suscripción" y "Productos vendidos" están vacías para todas las filas

4. **Caso borde — contacto sin vendedor asignado:**
   - Exportar una campaña que tiene contactos sin asignar
   - **Verificar:** La columna Vendedor está vacía (no genera error) para esos contactos

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos
- No se necesitan cambios de configuración
- No hay comandos de gestión que ejecutar
- La funcionalidad está disponible inmediatamente después del despliegue

## 🎓 Decisiones de Diseño

- **Enfoque por parámetro GET (`?export=csv`)** en lugar de una URL separada: más simple, respeta automáticamente los filtros activos, sin cambios de enrutamiento necesarios
- **Diccionario masivo de suscripciones** en lugar de consultas por contacto: cantidad fija de consultas sin importar el tamaño de la campaña
- **`iterator(chunk_size=1000)`** para streaming eficiente en memoria en campañas grandes

---

**Fecha:** 2026-03-10
**Autor:** Trifero + programador AI en par
**Branch:** t1052
**Tipo de cambio:** Funcionalidad
**Módulos afectados:** Support, Gestión de Campañas
