# Permission to merge contacts

- **Date:** 2026-11-25
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#181
- **Type:** Feature
- **Component:** Core Models
- **Impact:** Permissions

## 🎯 Summary

The base has the logic to merge two contacts (`Contact.merge_other_contact_into_this`) but no permission for it, so a
customization package that exposes a merge screen could only gate it by group (for la diaria, Admins or superusers).
This change adds `core.can_merge_contacts` to the `Contact` model, the same way `core.can_merge_addresses` already
exists on `Address`, so the merge can be given to a group without making it Admin.

## ✨ Changes

### 1. The permission on `Contact`

**Files:** `core/models.py`, `core/migrations/0129_contact_can_merge_contacts.py`

```python
class Meta:
    ...
    permissions = [
        ("can_merge_contacts", _("Can merge contacts")),
    ]
```

The migration is an `AlterModelOptions`. Django creates the permission in `post_migrate`, and no group gets it.

### 2. Translation

**File:** `locale/es/LC_MESSAGES/django.po`

«Puede combinar contactos», next to «Puede combinar direcciones». The entry was added by hand: `makemessages` renumbers
every reference in the file and turns a small change into thousands of lines.

## 📁 Files Modified

- **`core/models.py`**: `permissions` in the `Meta` of `Contact`
- **`locale/es/LC_MESSAGES/django.po`**: Spanish translation of the permission
- **`tests/test_contact_merge.py`**: the permission exists on `core.contact`
- **`CHANGELOG.md`**: entry for this change

## 📁 Files Created

- **`core/migrations/0129_contact_can_merge_contacts.py`**: adds the permission to the `Meta`

## 🧪 Manual Testing

1. **Happy path:**
   - Run `python manage.py migrate`
   - In the admin, open a group
   - **Verify:** «core | contact | Can merge contacts» is in the list of available permissions
2. **Edge case:**
   - Check that no group has the permission right after migrating
   - **Verify:** the base does not use it on its own, so nothing changes for anyone until a package checks it

## 📝 Deployment Notes

- **Migrations required:** `python manage.py migrate`
- No settings
- In la diaria's package, the merge screen checks it (it/utopia-crm-ladiaria#181, branch
  `gl181-permiso-fusionar-contactos`). Merge this PR first. Merging them in the other order breaks nothing:
  `has_perm` returns `False` and only Admins and superusers can merge, as before.

## 🎓 Design Decisions

- **In the base and not in the package:** the merge logic lives in the base, next to the permission to merge
  addresses. A permission created by a package migration on the `core.contact` ContentType also works, but no model
  would declare it.

---

- **Date:** 2026-11-25
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl181-permiso-fusionar-contactos
- **Type:** Feature
- **Modules affected:** core
