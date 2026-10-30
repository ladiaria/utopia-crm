# Se quita el envío de newsletters del CRM al CMS, que estaba apagado

- **Fecha:** 2026-10-30
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl35-cleanup-desmapeo-nl
- **Tipo de cambio:** Refactor
- **Componente:** Core (modelos, signals), settings
- **Impacto:** Sincronización con el CMS, extensiones que importaban la función quitada

## 🎯 Resumen

Desde t1158 (en producción en la diaria desde el 2026-06-30) el CMS es la autoridad de las newsletters: el CRM las lee
y las edita a demanda por delta, y el envío completo viejo se apagó con `WEB_UPDATE_USER_NEWSLETTERS_ENABLED = False`.
Ese envío, `update_web_user_newsletters`, mandaba el espejo local de las newsletters del contacto en cada guardado de
`Contact`, y el CMS lo aplicaba con un `.set()`: un reemplazo total que borraba las newsletters que el CRM no espejaba.
El flag se mantuvo como kill switch de rollback mientras el cambio se asentaba en producción. Después de cuatro meses
sin incidentes, se quitan la función, su llamada desde `contact_post_save_signal` y el flag
(it/utopia-crm-ladiaria#35).

## ✨ Cambios

### 1. La función de envío

**Archivo:** `core/models.py`

Se borra `update_web_user_newsletters`, junto con el import de `json` que sólo usaba ella. `get_newsletter_products`
se queda: la siguen leyendo el espejo de newsletters y la API de la diaria.

### 2. Su llamada en cada guardado de `Contact`

**Archivo:** `core/signals.py`

`contact_post_save_signal` ya no la llama. El resto del signal no cambia: `update_web_user` sigue sincronizando con el
CMS los otros datos del contacto.

### 3. El flag

**Archivo:** `settings.py`

Se quita `WEB_UPDATE_USER_NEWSLETTERS_ENABLED` de los settings base. Ya nada lo lee, así que una instalación que todavía
lo tenga en `local_settings.py` no se ve afectada y puede borrar la línea.

### 4. Punto de extensión desactualizado en `CLAUDE.md`

**Archivo:** `CLAUDE.md`

Los patrones de extensión nombraban `CORE_DEFAULT_NEWSLETTERS`, un setting que t1158 ya había quitado del código.

## 📁 Archivos Modificados

- **`core/models.py`** — se quitan `update_web_user_newsletters` y el import de `json` sin uso.
- **`core/signals.py`** — se quitan la llamada y el import en `contact_post_save_signal`.
- **`settings.py`** — se quita `WEB_UPDATE_USER_NEWSLETTERS_ENABLED`.
- **`CLAUDE.md`** — se quita `CORE_DEFAULT_NEWSLETTERS` de los patrones de extensión.

## 📚 Detalles Técnicos

**Lo que se queda.** `update_web_user` conserva sus parámetros `newsletter_data` / `area_newsletters`, y no se tocan
el espejo `SubscriptionNewsletter`, su admin ni el filtro por newsletter. Siguen congelados hasta la reconciliación de
newsletters, que repuebla el espejo desde el CMS.

**Donde el flag estaba en `False`, el comportamiento no cambia.** La función salía temprano, así que quitarla no cambia
nada. Donde el flag no estaba o estaba en `True` (su default viejo), cada guardado de `Contact` deja de pisar las
newsletters del CMS, que es el modelo buscado.

## 🧪 Pruebas Manuales

1. **Guardar un contacto sigue sincronizando sus datos:**
   - Con `WEB_UPDATE_USER_ENABLED = True`, cambiar el nombre de un contacto vinculado a una cuenta del CMS y guardar.
   - **Verificar:** el nombre cambia en el CMS, y las newsletters de esa persona en el CMS quedan como estaban.

2. **Las newsletters se siguen editando contra el CMS:**
   - Abrir las newsletters de un contacto en el CRM, agregar una y quitar otra.
   - **Verificar:** los dos cambios llegan al CMS y ninguna otra newsletter de la persona cambia.

3. **Caso borde — un `local_settings.py` viejo con el flag:**
   - Dejar `WEB_UPDATE_USER_NEWSLETTERS_ENABLED = False` (o `True`) en `local_settings.py` y correr
     `python manage.py check`.
   - **Verificar:** no hay errores, y en ninguno de los dos casos guardar un contacto manda newsletters al CMS.

## 📝 Notas de Despliegue

- No se requieren migraciones.
- Un paquete de customización que importe `update_web_user_newsletters` tiene que sacar ese import en el mismo deploy,
  o falla al arrancar con un `ImportError`. En la diaria, `utopia-crm-ladiaria` va junto con este cambio.
- Después del deploy, `WEB_UPDATE_USER_NEWSLETTERS_ENABLED` se puede borrar de `local_settings.py`.

---

- **Fecha:** 2026-10-30
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl35-cleanup-desmapeo-nl
- **Tipo de cambio:** Refactor
- **Módulos afectados:** Core, Settings
