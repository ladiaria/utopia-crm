# Permission to view metrics

- **Date:** 2026-11-27
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#205
- **Type:** Feature
- **Component:** Core / permissions
- **Impact:** Access control

## 🎯 Summary

A customization package may have metrics screens that some people need to see without being in a group that grants
much more (finances, administration). This change declares the permission `core.can_view_metrics` («Can view metrics»,
«Puede ver métricas») so those screens can ask for it.

The base repo only declares it. Nothing in the base checks it: la diaria's package uses it for its Métricas menu.

## ✨ Changes

### 1. The permission

**File:** `core/models.py`

Added to `Subscription.Meta.permissions`, next to `can_activate_in_web`:

```python
("can_view_metrics", _("Can view metrics")),
```

It goes in the base model, like the other permissions of the CRM's screens, so it is declared next to its model and
not created loose in the database by a package migration.

### 2. Migration and translation

- **`core/migrations/0131_subscription_can_view_metrics.py`**: `AlterModelOptions` on `subscription`. It does not
  change any table; Django creates the permission row after migrating.
- **`locale/es/LC_MESSAGES/django.po`**: «Puede ver métricas», added by hand (`makemessages` renumbers the whole
  file).

## 📁 Files Modified

- **`core/models.py`**: the permission
- **`locale/es/LC_MESSAGES/django.po`**: its translation
- **`CHANGELOG.md`**: entry for this change

## 📁 Files Created

- **`core/migrations/0131_subscription_can_view_metrics.py`**: the migration

## 🧪 Manual Testing

1. **Happy path:**
   - Run `python manage.py migrate core`
   - **Verify:** in the admin, Users → a user → Permissions lists «core | subscription | Puede ver métricas»
2. **Edge case:**
   - Run `python manage.py makemigrations --settings=migration_settings core --check`
   - **Verify:** no changes are detected

## 📝 Deployment Notes

- Run `python manage.py migrate` after deploying: the permission does not exist until then, so it can only be
  assigned afterwards
- Assign it by hand in the admin, to a group or a user. No data migration assigns it

## 🎓 Design Decisions

- **In `Subscription` and not in a model of the package:** the CRM's permissions live in the `Meta` of the base model,
  as `can_activate_in_web` and `can_export_contacts` do. Metrics are about subscriptions.
- **No check in the base:** the screens that use it are in the customization package.

---

- **Date:** 2026-11-27
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl205-permiso-ver-metricas
- **Type:** Feature
- **Modules affected:** core
