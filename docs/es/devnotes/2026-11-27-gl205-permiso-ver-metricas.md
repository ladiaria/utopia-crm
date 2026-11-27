# Permiso para ver métricas

- **Fecha:** 2026-11-27
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#205
- **Tipo:** Funcionalidad
- **Componente:** Core / permisos
- **Impacto:** Control de acceso

## 🎯 Resumen

Un paquete de customización puede tener pantallas de métricas que algunas personas necesitan ver sin estar en un grupo
que les da mucho más (finanzas, administración). Este cambio declara el permiso `core.can_view_metrics` («Can view
metrics», «Puede ver métricas») para que esas pantallas lo puedan pedir.

El repo base sólo lo declara. Nada en el base lo chequea: lo usa el paquete de la diaria para su menú de Métricas.

## ✨ Cambios

### 1. El permiso

**Archivo:** `core/models.py`

Se agregó a `Subscription.Meta.permissions`, junto a `can_activate_in_web`:

```python
("can_view_metrics", _("Can view metrics")),
```

Va en el modelo del base, como los demás permisos de las pantallas del CRM, así queda declarado junto a su modelo y no
creado suelto en la base por una migración del paquete.

### 2. Migración y traducción

- **`core/migrations/0131_subscription_can_view_metrics.py`**: `AlterModelOptions` sobre `subscription`. No cambia
  ninguna tabla; Django crea la fila del permiso después de migrar.
- **`locale/es/LC_MESSAGES/django.po`**: «Puede ver métricas», agregada a mano (`makemessages` renumera todo el
  archivo).

## 📁 Archivos modificados

- **`core/models.py`**: el permiso
- **`locale/es/LC_MESSAGES/django.po`**: su traducción
- **`CHANGELOG.md`**: entrada de este cambio

## 📁 Archivos creados

- **`core/migrations/0131_subscription_can_view_metrics.py`**: la migración

## 🧪 Pruebas manuales

1. **Camino feliz:**
   - Correr `python manage.py migrate core`
   - **Verificar:** en el admin, Usuarios → un usuario → Permisos aparece «core | subscription | Puede ver métricas»
2. **Caso borde:**
   - Correr `python manage.py makemigrations --settings=migration_settings core --check`
   - **Verificar:** no detecta cambios

## 📝 Notas de despliegue

- Correr `python manage.py migrate` después del deploy: el permiso no existe hasta entonces, así que recién después se
  puede asignar
- Se asigna a mano en el admin, a un grupo o a un usuario. Ninguna migración de datos lo asigna

## 🎓 Decisiones de diseño

- **En `Subscription` y no en un modelo del paquete:** los permisos del CRM viven en el `Meta` del modelo del base,
  como `can_activate_in_web` y `can_export_contacts`. Las métricas son de suscripciones.
- **Sin chequeo en el base:** las pantallas que lo usan están en el paquete de customización.

---

- **Fecha:** 2026-11-27
- **Autora:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl205-permiso-ver-metricas
- **Tipo:** Funcionalidad
- **Módulos afectados:** core
