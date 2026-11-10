# The "Contact filters" screens are retired from Support

- **Date:** 2026-11-10
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#116
- **Type:** Refactor
- **Component:** Support, Core
- **Impact:** User Experience, Maintenance

## 🎯 Summary

The **Support » Contact filters** screens (`DynamicContactFilter`) were built to keep lists that synced themselves with Mailtrain, not to filter contacts. People kept using them to filter contacts, and they were broken: editing a filter raised a 500 in production, and creating one raised another. Instead of fixing a feature nobody should be using, this removes its screens and its Mailtrain commands. The model and its admin stay, so the 44 filters saved in production are not lost and there is no migration.

## ✨ Changes

### 1. The screens and the menu entry go away

**Files:** `support/views/all_views.py`, `support/urls.py`, `support/forms.py`, `templates/components/sidebar_items/_support.html`

The six views (`dynamic_contact_filter_new`, `dynamic_contact_filter_list`, `dynamic_contact_filter_edit`, `export_dcf_emails`, `advanced_export_dcf_list`, `sync_with_mailtrain`), their URLs, `NewDynamicContactFilterForm`, the three templates and the sidebar entry are removed. Old URLs now return 404.

Both forms of the screen were broken:

- **Edit** assigned a many-to-many directly, which Django forbids since 2.0. It raised `TypeError: Direct assignment to the forward side of a many-to-many set is prohibited` from the 2024-11-02 refactor on:

  ```python
  dcf.products = products  # needs dcf.products.set(products)
  ```

- **Create** used `debtor_contacts` without reading it from the form, so the preview step raised `NameError`.

On top of that, the newsletters mode reads `SubscriptionNewsletter`, a mirror that is no longer updated, so its counts were stale even when the screen worked.

### 2. The Mailtrain commands go away

**Files:** `support/management/commands/sync_all_filters.py`, `support/management/commands/sync_one_filter.py`, `core/management/commands/synchronize_contact_filters_mailtrain.py`

The three commands synced filters with Mailtrain lists. Only `synchronize_contact_filters_mailtrain` was ever in la diaria's cron, and it has been commented out for a long time. In production no filter has `autosync`, and the last sync was on 2023-03-20.

### 3. The model, its admin and its tests stay

**Files:** `core/models.py`, `core/admin.py`, `tests/test_dynamiccontactfilter.py` (unchanged)

`DynamicContactFilter` keeps its fields and methods, including `sync_with_mailtrain_list`. Saved filters can still be looked up from the admin, and the model tests still pass.

## 📁 Files Modified

- **`support/views/all_views.py`** — The six views and their unused imports removed
- **`support/urls.py`** — Their URLs removed
- **`support/forms.py`** — `NewDynamicContactFilterForm` removed
- **`templates/components/sidebar_items/_support.html`** — The "Contact filters" entry removed
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Deleted

- **`support/templates/dynamic_contact_filter.html`** — Create screen
- **`support/templates/dynamic_contact_filter_details.html`** — Edit screen
- **`support/templates/dynamic_contact_filter_list.html`** — List screen
- **`support/management/commands/sync_all_filters.py`** — Mailtrain sync of every `autosync` filter
- **`support/management/commands/sync_one_filter.py`** — Mailtrain sync of one filter
- **`core/management/commands/synchronize_contact_filters_mailtrain.py`** — Same as `sync_all_filters`, the one in the cron

## 🧪 Manual Testing

1. **Happy path, the menu:**
   - Open the **Support** menu.
   - **Verify:** "Contact filters" is not there, and the rest of the entries (including those of a customization package) are.

2. **Edge case, an old bookmark:**
   - Open `/support/dynamic_contact_filter/5/` or `/support/dynamic_contact_filter_list/`.
   - **Verify:** 404.

3. **Edge case, saved filters:**
   - Open **Admin » Core » Dynamic Contact Filters**.
   - **Verify:** The saved filters are listed and can be opened.

## 📝 Deployment Notes

- No database migrations required.
- After deploying, remove the commented `synchronize_contact_filters_mailtrain` line from the cron (la diaria: `ss_conf/etc/cron.d/crm`). The command no longer exists, so uncommenting it would fail.
- Deployed to la diaria's production on 2026-11-10 (`b00e68c0`).

## 🚀 Future Improvements

- Drop the `DynamicContactFilter` model, its admin, its test and its factory, with a migration.

## 🎓 Design Decisions

- **Retire it instead of fixing it:** fixing the two 500s would bring back a screen that filters on fewer criteria than the contact filter people should be using, with stale newsletter data. Fixing it would also keep inviting its use.
- **No feature flag:** a flag would keep broken code alive that nobody would fix.
- **No redirect:** an old bookmark gets a 404, so people learn the screen is gone.
- **Keep the model for now:** the saved filters stay readable and the deploy needs no migration.

---

- **Date:** 2026-11-10
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl116-retirar-filtros-de-contactos
- **Type:** Refactor
- **Modules affected:** support, core, templates
