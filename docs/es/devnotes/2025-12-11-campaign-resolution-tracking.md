# Seguimiento de Resolución de Campañas en Consola de Vendedor

**Fecha:** 2025-12-11
**Tipo:** Mejora de Funcionalidad, Seguimiento de Datos
**Componente:** Consola de Vendedor, Gestión de Campañas
**Impacto:** Analíticas de Campañas, Reportes
**Tarea:** t982

## Resumen

Se mejoró la consola de vendedor para rastrear correctamente las resoluciones de campañas agregando un campo `campaign_resolution` al modelo `SellerConsoleAction`. Esto asegura que cuando los vendedores toman acciones (ej. "no interesado", "no llamar", "logística"), el sistema ahora registra tanto el estado de la campaña como la razón específica de resolución, permitiendo un seguimiento completo de los resultados de las campañas y analíticas.

## Motivación

La consola de vendedor solo estaba rastreando parcialmente los resultados de las campañas:

1. **Seguimiento incompleto:** Solo se establecía `campaign_status` (ej. ENDED_WITH_CONTACT), pero `campaign_resolution` permanecía nulo
2. **Datos de resolución faltantes:** El campo `campaign_resolution` solo se establecía por `mark_as_sale` (a "S2"), pero nunca para acciones de rechazo/sin contacto
3. **Analíticas limitadas:** Sin datos de resolución, era imposible analizar por qué terminaban las campañas (no interesado vs. no llamar vs. logística, etc.)
4. **Datos inconsistentes:** El dropdown `resolution_reason` se guardaba, pero el campo principal `campaign_resolution` no

Esto dificultaba generar reportes significativos sobre los resultados de las campañas y entender por qué los contactos estaban rechazando o eran inalcanzables.

## Implementación

### 1. Campo `campaign_resolution` Agregado al Modelo `SellerConsoleAction`

**Archivo:** `support/models.py`

Se agregó un nuevo campo para almacenar qué resolución de campaña debe establecerse cuando se realiza cada acción:

```python
class SellerConsoleAction(models.Model):
    # ... campos existentes ...
    campaign_resolution = models.CharField(
        max_length=2,
        choices=CAMPAIGN_RESOLUTION_CHOICES,
        null=True,
        blank=True,
        help_text=_("Campaign resolution to set when this action is performed"),
    )
```

**Mapeo de Códigos de Resolución:**

- `NI` - No interesado
- `DN` - No llamar más
- `LO` - Logística
- `AS` - Ya es suscriptor
- `EP` - Error en promoción
- `UN` - No se puede encontrar contacto
- `CW` - Cerrar sin contacto
- `SC` - Agendado
- `CL` - Llamar más tarde

### 2. Método `process_activity_result` Actualizado

**Archivo:** `support/views/seller_console.py`

Se mejoró el método para establecer `campaign_resolution` desde la acción:

```python
def process_activity_result(self, contact, campaign, seller, seller_console_action, notes):
    # ... código existente ...

    # Usar el campaign_status de la acción si está establecido
    if seller_console_action.campaign_status:
        ccs.status = seller_console_action.campaign_status

    # Usar el campaign_resolution de la acción si está establecido
    if seller_console_action.campaign_resolution:
        ccs.campaign_resolution = seller_console_action.campaign_resolution

    return ccs
```

### 3. Comando de Gestión Mejorado

**Archivo:** `core/management/commands/populate_seller_console_actions.py`

Se actualizó el comando para poblar valores de `campaign_resolution` para cada acción:

**Cambios:**

- Estructura de tupla expandida de 4-tupla a 5-tupla: `(action_type, slug, action_name, campaign_status, campaign_resolution)`
- Se agregaron códigos de resolución para cada acción
- Salida actualizada para mostrar tanto estado como resolución

**Mapeos de Acciones:**

| Acción | Slug | Estado de Campaña | Resolución de Campaña |
|--------|------|-------------------|----------------------|
| Llamar más tarde | `call-later` | CALLED_COULD_NOT_CONTACT (3) | CL |
| Mover a la mañana | `move-morning` | SWITCH_TO_MORNING (6) | None |
| Mover a la tarde | `move-afternoon` | SWITCH_TO_AFTERNOON (7) | None |
| No interesado | `not-interested` | ENDED_WITH_CONTACT (4) | NI |
| No llamar | `do-not-call` | ENDED_WITH_CONTACT (4) | DN |
| Logística | `logistics` | ENDED_WITH_CONTACT (4) | LO |
| Ya suscrito | `already-subscriber` | ENDED_WITH_CONTACT (4) | AS |
| Error en promoción | `error-promotion` | ENDED_WITHOUT_CONTACT (5) | EP |
| No contactable | `uncontactable` | ENDED_WITHOUT_CONTACT (5) | UN |
| Cerrar sin contacto | `close-without-contact` | ENDED_WITHOUT_CONTACT (5) | CW |
| Agendar | `schedule` | CONTACTED (2) | SC |

**Nota:** Los movimientos de mañana/tarde no tienen resolución ya que son acciones pendientes, no resultados finales.

### 4. Estructura de Plantilla de Consola de Vendedor Corregida

**Archivo:** `support/templates/seller_console.html`

Se corrigieron problemas críticos de estructura HTML que impedían el envío del formulario:

**Problemas Corregidos:**

1. **Etiqueta de cierre de formulario faltante:** La etiqueta `<form>` se abría en la línea 256 pero nunca se cerraba correctamente
2. **Div de cierre huérfano:** Etiqueta `</div>` extra sin etiqueta de apertura correspondiente
3. **Envío de formulario roto:** El campo `campaign_resolution_reason` no se enviaba debido a HTML malformado

**Cambios:**

- Se agregó etiqueta de cierre `</form>` apropiada después de todas las entradas y botones del formulario
- Se eliminó etiqueta `</div>` huérfana
- Se corrigió indentación y anidación de columna de barra lateral

Esto asegura que cuando los usuarios seleccionan una razón de resolución del dropdown y hacen clic en un botón de acción, todos los datos del formulario (incluyendo `campaign_resolution_reason`) se envían correctamente.

## Cambios en Base de Datos

### Migración: `support/migrations/0031_sellerconsoleaction_campaign_resolution_and_more.py`

**Cambios:**

- Se agregó campo `campaign_resolution` al modelo `SellerConsoleAction`
- El campo es nullable y opcional para compatibilidad hacia atrás
- Usa `CAMPAIGN_RESOLUTION_CHOICES` para validación

## Flujo de Datos

Cuando un vendedor toma una acción en la consola de vendedor:

1. **Usuario hace clic en botón de acción** (ej. "No interesado")
2. **Formulario se envía** con:
   - `result` = slug de acción (ej. "not-interested")
   - `campaign_resolution_reason` = valor opcional del dropdown
   - `notes` = notas de actividad
3. **`handle_post_request` procesa:**
   - Busca `SellerConsoleAction` por slug
   - Llama a `process_activity_result`
4. **`process_activity_result` establece:**
   - `ccs.status` = `seller_console_action.campaign_status` (ej. 4 = ENDED_WITH_CONTACT)
   - `ccs.campaign_resolution` = `seller_console_action.campaign_resolution` (ej. "NI")
   - `ccs.resolution_reason` = del dropdown (si se seleccionó)
   - `ccs.last_console_action` = el objeto de acción
5. **`ccs.save()`** persiste todos los datos de seguimiento

## Seguimiento Completo

El sistema ahora rastrea tres niveles de información de resultado de campaña:

1. **`campaign_status`** (entero): Estado de alto nivel (contactado, terminado con contacto, terminado sin contacto, etc.)
2. **`campaign_resolution`** (código de 2 caracteres): Razón específica de resultado (NI, DN, LO, AS, EP, UN, CW, SC, CL)
3. **`resolution_reason`** (entero): Razón detallada opcional del dropdown (específica del proyecto)
4. **`last_console_action`** (FK): Qué botón se presionó

## Beneficios

### 1. Analíticas Completas de Campañas

- Rastrear exactamente por qué terminaron las campañas (no interesado vs. no llamar vs. logística)
- Analizar patrones en respuestas de contactos
- Generar reportes detallados de resultados

### 2. Mejores Reportes

- Las estadísticas de campaña ahora muestran datos completos de resolución
- Los gerentes pueden ver desglose de razones de rechazo
- Los datos de exportación incluyen toda la información de resolución

### 3. Consistencia de Datos

- Todas las acciones de consola de vendedor ahora establecen resoluciones apropiadas
- No más campos `campaign_resolution` nulos para contactos rechazados
- Estructura de datos consistente en todas las campañas

### 4. Envío de Formulario Mejorado

- Estructura HTML corregida asegura que todos los datos del formulario se envíen
- El dropdown de razón de resolución ahora funciona correctamente
- No más pérdida de datos del formulario debido a HTML malformado

## Uso

### Para Desarrolladores

**Ejecutando el comando de gestión:**

```bash
python manage.py populate_seller_console_actions
```

Esto actualizará todos los registros existentes de `SellerConsoleAction` con valores apropiados de `campaign_resolution`.

### Para Gerentes

Las estadísticas y reportes de campañas ahora incluyen datos completos de resolución:

- Ver por qué los contactos rechazaron (no interesado, no llamar, logística, etc.)
- Analizar efectividad de campaña por tipo de resolución
- Exportar datos detallados de resultados para análisis

### Para Vendedores

Sin cambios en el flujo de trabajo - los vendedores continúan usando los mismos botones, pero ahora el sistema rastrea información completa de resultados automáticamente.

## Pruebas

### Pasos de Verificación

1. **Verificar configuración de acciones:**

   ```python
   from support.models import SellerConsoleAction
   actions = SellerConsoleAction.objects.all()
   for action in actions:
       print(f"{action.slug}: status={action.campaign_status}, resolution={action.campaign_resolution}")
   ```

2. **Probar consola de vendedor:**
   - Abrir consola de vendedor para cualquier campaña
   - Hacer clic en botón "No interesado"
   - Verificar en base de datos:

     ```sql
     SELECT status, campaign_resolution, resolution_reason, last_console_action_id
     FROM core_contactcampaignstatus
     WHERE contact_id = <contact_id> AND campaign_id = <campaign_id>;
     ```

   - Debería mostrar: `status=4, campaign_resolution='NI'`

3. **Verificar estadísticas de campaña:**
   - Ver página de detalle de estadísticas de campaña
   - Verificar que se muestren datos de resolución
   - Exportar CSV y verificar columna de resolución

## Archivos Modificados

- `support/models.py` - Campo `campaign_resolution` agregado
- `support/views/seller_console.py` - Método `process_activity_result` actualizado
- `core/management/commands/populate_seller_console_actions.py` - Mejorado con mapeo de resolución
- `support/templates/seller_console.html` - Estructura HTML corregida
- `support/migrations/0031_sellerconsoleaction_campaign_resolution_and_more.py` - Migración de base de datos

## Compatibilidad Hacia Atrás

- Los registros existentes de `SellerConsoleAction` se actualizan automáticamente por el comando de gestión
- El campo nullable asegura que no haya problemas con datos existentes
- El código antiguo continúa funcionando (simplemente no establece resolución)
- Sin cambios que rompan la API o vistas

## Mejoras Futuras

Posibles mejoras para iteraciones futuras:

1. **Panel de analíticas de resolución:** Vista dedicada mostrando desgloses de resolución
2. **Filtrado basado en resolución:** Filtrar campañas por tipo de resolución
3. **Reportes automatizados:** Reportes programados mostrando tendencias de resolución
4. **Recomendaciones de resolución:** Sugerir acciones basadas en historial de contacto

## Problemas Relacionados

- Corrige seguimiento incompleto de resultados de campaña
- Resuelve campos `campaign_resolution` nulos para contactos rechazados
- Aborda problemas de envío de formulario en plantilla de consola de vendedor

## Notas

- El campo `resolution_reason` (dropdown) es separado y opcional - proporciona detalle adicional específico del proyecto
- Los movimientos de mañana/tarde intencionalmente no tienen resolución ya que son acciones pendientes, no resultados finales
- El comando de gestión es idempotente y seguro de ejecutar múltiples veces
