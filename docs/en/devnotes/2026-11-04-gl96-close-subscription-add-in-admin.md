# Subscriptions can no longer be added from the admin

- **Date:** 2026-11-04
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl96-cerrar-alta-suscripcion-admin (it/utopia-crm-ladiaria#96)
- **Type:** Bug Fix
- **Component:** Core (subscription admin)
- **Impact:** Performance, Data Integrity

## 🎯 Summary

Subscriptions are created from the contact, but the admin still offered its own add page. Nobody should use it: it skips that flow and builds a dropdown with every address in the database, the same kind of page that ran the production server out of memory in gl96. The add page is now closed for everyone, superusers included, and the admin form can no longer list every address.

## ✨ Changes

### 1. The add page is closed

**File:** `core/admin.py`

`SubscriptionAdmin.has_add_permission` returns `False`. The admin checks this method before looking at the permissions of the user, so a superuser gets a 403 too, and the add button disappears from the list. Customization packages that subclass `SubscriptionAdmin` inherit it.

### 2. The dropdown never lists the whole table

**File:** `core/forms.py`

`SubscriptionAdminForm` only filtered `billing_address` when it had an instance. Without one, it now lists no addresses:

```python
self.fields['billing_address'].queryset = (
    Address.objects.filter(contact=instance.contact) if instance else Address.objects.none()
)
```

Editing a subscription works as before, with the addresses of its contact.

### 3. Tests

**File:** `tests/test_subscription_admin.py`

A superuser gets a 403 with GET and POST and nothing is created, the list has no add button, the change page only lists the addresses of the contact, and the form without a subscription lists none.

## 📁 Files Modified

- **`core/admin.py`** — `has_add_permission` in `SubscriptionAdmin`.
- **`core/forms.py`** — `SubscriptionAdminForm` never lists every address.
- **`CHANGELOG.md`** — Entry.

## 📁 Files Created

- **`tests/test_subscription_admin.py`** — Tests of the closed add page and the dropdown.
- **`docs/en/devnotes/2026-11-04-gl96-close-subscription-add-in-admin.md`** — This devnote.
- **`docs/es/devnotes/2026-11-04-gl96-cerrar-alta-de-suscripciones-en-admin.md`** — Spanish version.

## 🧪 Manual Testing

1. **Editing still works (happy path):**
   - As a superuser, open a subscription in the admin (`/admin/core/subscription/<id>/change/`).
   - **Verify:** the page loads quickly, and the billing address dropdown only has the addresses of its contact.

2. **The add page is closed, even for a superuser (edge case):**
   - As a superuser, open the subscription list in the admin, then go to `/admin/core/subscription/add/`.
   - **Verify:** the list has no add button, and the URL answers 403.

3. **The usual flow:**
   - Create a subscription from the contact detail.
   - **Verify:** it works as before.

## 📝 Deployment Notes

- No database migrations required.
- No new translations.

---

- **Date:** 2026-11-04
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl96-cerrar-alta-suscripcion-admin
- **Type:** Bug Fix
- **Modules affected:** Core
