# Three new permissions and access checks that did not do what they seemed to

- **Date:** 2026-11-25
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#183, #184
- **Type:** Bug Fix / Feature
- **Component:** Core Models, Support
- **Impact:** Permissions, Security

## 🎯 Summary

A review of every access check in the CRM found buttons hidden from a group while their view stayed open, views with
no login at all, and a group name misspelled. This change fixes the ones in the base and adds three permissions, so a
customization package can give a group that is not Admins what today only Admins or Managers can do.

## ✨ Changes

### 1. Three new permissions

**Files:** `core/models.py`, `core/migrations/0130_permisos_exportar_no_llamar_activar.py`

| Permission | Model | What it lets |
|---|---|---|
| `core.can_export_contacts` | `Contact` | Export the contact list to CSV |
| `core.can_activate_in_web` | `Subscription` | Checked by packages that activate a subscription in the web on demand |
| `core.can_upload_do_not_call_numbers` | `DoNotCallNumber` | Upload the do not call list |

No group gets them when migrating. Admins and superusers keep passing without them.

### 2. Contact list export

**Files:** `support/views/contacts.py`, `support/templates/contact_list.html`

The «Export to CSV» button was shown only to Managers, but `ContactListView.get` exported for any staff user with
`?export=…`. `user_can_export_contacts(user)` now checks it in the view: Managers (through `in_group`, which also lets
Admins and superusers in) or `core.can_export_contacts`. Otherwise, 403. The button follows the same rule.

### 3. Do not call list

**Files:** `support/views/all_views.py`, `templates/components/sidebar_items/_campaign_management.html`,
`support/templates/campaign_management_menu.html`

`upload_do_not_call_numbers` lets in Admins, superusers and `core.can_upload_do_not_call_numbers`, and so do its link
and its card. The «Bulk Delete Campaign Status» link and card are now shown only to Admins, the same as the view: a
Manager could see them but not use them.

### 4. Views that now ask for staff

**Files:** `support/views/contacts.py`, `support/views/all_views.py`

`contact_invoices_htmx` and `contact_activities_htmx` only checked the `HX-Request` header, which anyone can send, and
`api_new_address` created an address on any contact. The three now have `@staff_member_required`, and
`api_new_address` also `@require_POST`: it only does something on a POST, and no template nor other system calls it
today.

None of them is an external API. The two htmx views are loaded by the CRM page itself, from the browser of the user
looking at the contact, so the session goes with the request and the decorator does not break them. Their docstrings
now say so.

### 5. Group names

**Files:** `support/views/contacts.py`, `support/templates/location/editar_direccion.html`,
`support/templates/location/agregar_direccion.html`

- Editing a contact's campaign status asked for `Managers` or `Admin`. The group is `Admins`, so Admins could not.
- The manual address search was hidden with `{% if not … in_group:"Sellers" %}`. `in_group` lets Admins in, so it was
  hidden from Admins too. It now hides only from real Sellers members who are not Admins.

## 📁 Files Modified

- **`core/models.py`**: the three permissions
- **`locale/es/LC_MESSAGES/django.po`**: their translations, added by hand
- **`support/views/contacts.py`**: export check, campaign status group, staff on the two htmx views
- **`support/views/all_views.py`**: do not call permission, staff on `api_new_address`
- **`support/templates/contact_list.html`**, **`support/templates/campaign_management_menu.html`**,
  **`templates/components/sidebar_items/_campaign_management.html`**, **`support/templates/location/editar_direccion.html`**,
  **`support/templates/location/agregar_direccion.html`**
- **`tests/test_upload_do_not_call_numbers.py`**: the permission lets a non-Admin upload
- **`CHANGELOG.md`**

## 📁 Files Created

- **`core/migrations/0130_permisos_exportar_no_llamar_activar.py`**
- **`tests/test_access_checks.py`**: export, campaign status and the campaign management sidebar

## 🧪 Manual Testing

1. **Happy path:**
   - Give a non-Admin Manager «Can export contacts» and «Can upload the do not call list»
   - **Verify:** they can export the contact list and see and use «Upload do not call list»
2. **Edge case:**
   - As a Support user, open `/support/contacts/?export=1`
   - **Verify:** 403, nothing is downloaded. Without `export`, the list opens as before

## 📝 Deployment Notes

- **Migrations required:** `python manage.py migrate`
- Merge before the la diaria package MR, which checks `core.can_activate_in_web` and `core.can_export_contacts`.
  In the other order nothing breaks: without the permissions only Admins, superusers and Managers pass, as before.

## 🎓 Design Decisions

- **The other base exports stay open to staff** (subscription end dates, issues, debtors, scheduled tasks): their
  buttons were never hidden from anyone.
- **`can_activate_in_web` lives on `Subscription`** even though the base does not use it, next to the other
  subscription permissions, the same way `can_merge_contacts` lives on `Contact`.

---

- **Date:** 2026-11-25
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl183-permisos-y-chequeos-de-acceso
- **Type:** Bug Fix / Feature
- **Modules affected:** core, support
