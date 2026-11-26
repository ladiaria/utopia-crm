# Borrar una suscripción conserva sus incidencias

- **Fecha:** 2026-11-26
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#192
- **Tipo:** Corrección de error
- **Componente:** Support, Incidencias
- **Impacto:** Integridad de datos, Permisos

## 🎯 Resumen

`Issue.subscription` era `on_delete=CASCADE`, así que borrar una suscripción borraba sus incidencias y, con ellas,
sus actividades (`Activity.issue` también es `CASCADE`). Las incidencias y las actividades son la historia del
contacto y tienen que sobrevivir a la suscripción. La cascada también tenía un efecto en los permisos: el admin de
Django exige el permiso de borrado de cada objeto que la cascada va a borrar, así que un usuario con
`delete_subscription` no podía borrar una suscripción con incidencias si no tenía también `delete_issue` y
`delete_activity`. Se detectó cuando dos usuarios de un grupo con permisos de admin acotados no podían borrar
suscripciones.

Este cambio pasa `Issue.subscription` a `SET_NULL`. Las tareas programadas y los registros de venta mantienen la
cascada a propósito.

## ✨ Cambios

### 1. `Issue.subscription` pasa a `SET_NULL`

**Archivo:** `support/models.py`

```python
subscription = models.ForeignKey(
    "core.Subscription", verbose_name=_("Subscription"), on_delete=models.SET_NULL, null=True, blank=True
)
```

El campo ya era `null=True` y hay muchas incidencias sin suscripción, así que el código que lee
`issue.subscription` ya contempla el `None`. Como la incidencia ya no se borra, sus actividades también quedan.

### 2. Migración

**Archivo:** `support/migrations/0045_issue_subscription_set_null.py`

Un `AlterField` que sólo cambia `on_delete`. Django aplica el `on_delete` en Python, no en la base de datos, así que
la migración no altera la tabla.

## 📁 Archivos Modificados

- **`support/models.py`**: `Issue.subscription` pasa de `CASCADE` a `SET_NULL`
- **`CHANGELOG.md`**: entrada de este cambio

## 📁 Archivos Creados

- **`support/migrations/0045_issue_subscription_set_null.py`**: la migración
- **`tests/test_subscription_delete_keeps_issues.py`**: borrar una suscripción conserva su incidencia (sin
  suscripción) y la actividad de la incidencia, y sigue borrando sus tareas programadas y registros de venta

## 🧪 Pruebas Manuales

1. **Caso normal:**
   - Correr `python -W ignore manage.py test --settings=test_settings --keepdb tests.test_subscription_delete_keeps_issues`
   - **Verificar:** los dos tests pasan
2. **Desde el admin, con una suscripción que tiene una incidencia con actividades:**
   - Abrir la suscripción en el admin y hacer clic en «Eliminar»
   - **Verificar:** la página de confirmación ya no lista la incidencia ni sus actividades y, después de borrar, la
     incidencia sigue en la ficha del contacto, sin suscripción
3. **Caso borde, un usuario sin `delete_issue` ni `delete_activity`:**
   - Entrar con un usuario que tenga `delete_subscription` y el permiso de borrado de los demás objetos
     relacionados, pero no esos dos, y borrar una suscripción con incidencias
   - **Verificar:** el admin lo deja borrar

## 📝 Notas de Despliegue

- Se requieren migraciones: `python manage.py migrate`. No altera ninguna tabla
- Sin cambios de configuración

## 🎓 Decisiones de Diseño

- **Las tareas programadas y los registros de venta mantienen `CASCADE`:** sin la suscripción no tienen sentido.
  Además, una tarea programada pendiente sin suscripción fallaría todos los días en `run_scheduled_tasks`, porque
  `execute()` escribe en `self.subscription`. Un registro de venta sin suscripción rompería el filtro de registros de
  venta y sus exportaciones, que leen `sr.subscription.contact_id` y `sr.subscription.start_date`.
- **`Activity.issue` no cambia:** si la incidencia sobrevive a la suscripción, sus actividades también. Borrar una
  incidencia directamente sigue borrando sus actividades, como antes.

---

- **Fecha:** 2026-11-26
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl192-incidencias-sin-cascada
- **Tipo de cambio:** Corrección de error
- **Módulos afectados:** Support
