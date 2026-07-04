# Newsletters Unmapping: CMS Becomes the Source of Truth

- **Date:** 2026-06-29
- **Author:** Tanya Tree + Claude Opus 4.8
- **Ticket:** t1158 (branch `desmapeo-newsletters`)
- **Type:** Refactor
- **Component:** Core, Support, Invoicing, Settings, Contact templates
- **Impact:** Data Integrity, User Experience, CRM↔CMS sync

## 🎯 Summary

The CRM used to keep a local mirror of each contact's newsletters (`SubscriptionNewsletter`) and treat it as the truth: on every `Contact` save it pushed the full photo to the CMS with a destructive `.set()`, which overwrote newsletters the CRM didn't know about. This work flips the model so the **CMS is the source of truth**. The CRM no longer trusts its mirror: it **reads and edits newsletters on demand** against the CMS over htmx (contact detail, edit-contact form, and the seller console), edits are applied as **non-destructive deltas** (add/remove a single newsletter), the destructive CRM→CMS push is turned off behind a flag, the rudimentary "default newsletters" dialog is removed (the CMS now applies its own defaults on account creation), and the now-unused newsletter maps are retired. The local mirror is intentionally left in place but frozen; the newsletter filter keeps reading it until a future repopulation command exists.

This is the base-app (`utopia-crm`) half of the change; it pairs with new read/delta REST endpoints in the CMS (`utopia-cms`) and must be deployed alongside them.

## ✨ Changes

### 1. On-demand newsletter read/edit via an htmx proxy

**Files:** `support/views/newsletters.py` (new), `support/urls.py`, `support/views/__init__.py`,
`support/templates/contact_detail/tabs/_overview.html`,
`support/templates/contact_detail/htmx/_newsletters_htmx.html` (new),
`support/templates/create_contact/tabs/_newsletters.html`,
`support/templates/create_contact/htmx/_newsletters_form_htmx.html` (new),
`support/templates/create_contact/htmx/_newsletter_item.html` (new),
`support/templates/create_contact/create_contact.html`, `support/views/contacts.py`

Three staff-only proxy views were added. The browser talks to the CRM (htmx); the CRM talks to the CMS with the API key it already holds server-side, via `cms_rest_api_request`:

- `contact_newsletters_overview` — read-only partial for the contact overview card.
- `contact_newsletters_form` — editable partial (checkboxes by type) for the edit-contact Newsletters tab.
- `contact_newsletter_toggle` — persists a single newsletter change straight to the CMS as a **delta**, independent of the contact form submit (so it never goes through `Contact.save()` nor the local mirror).

The contact overview card and the edit-contact Newsletters tab now load by AJAX (`hx-trigger`), splitting **Newsletters** (publication) from **Áreas** (category). The overview no longer precomputes the mirror (`get_all_querysets_and_lists`), and `ContactAdminFormWithNewsletters` was reduced to a plain form (its `newsletters` field and save were removed).

Two bugs were found and fixed while building the widget:

1. The htmx newsletter item must **not** inject submittable fields into the contact `<form>`: its hidden `name=...` inputs collided with the Contact's own `name` field, so saving the contact replaced the contact's name with a newsletter's. The item now carries no submittable inputs; the data travels only with the htmx request via `hx-vals` (namespaced `nl_*` keys).
2. `hx-vals='js:{...}'` does not bind `this` to the element in htmx 1.9.2, so `this.dataset` threw and **aborted the request** (the toggle never fired). The checkbox is now referenced by `id`.

### 2. Newsletters card in the seller console

**File:** `support/templates/seller_console.html`

A collapsible **Newsletters** card was added to the right sidebar, below the "Web Reading" card. It reuses the same `contact_newsletters_overview` proxy and read-only partial, loading by htmx — no new backend.

### 3. Destructive CRM→CMS push turned off behind a flag

**Files:** `core/models.py`, `settings.py`

`update_web_user_newsletters` now early-returns when `WEB_UPDATE_USER_NEWSLETTERS_ENABLED` is `False`. A single guard covers both signal callers. The setting defaults to `True` (backwards-compatible); production must set it to `False` so a `Contact` save no longer `.set()`s the CMS to the local mirror and wipes newsletters the CRM doesn't mirror.

```python
if not getattr(settings, "WEB_UPDATE_USER_NEWSLETTERS_ENABLED", True):
    return
```

### 4. The "default newsletters" dialog was removed

**Files:** `support/views/all_views.py`, `support/templates/default_newsletters_dialog.html` (deleted),
`core/models.py`, `core/admin.py`, `invoicing/api.py`, `settings.py`

The rudimentary dialog that asked whether to add the default newsletters on subscription creation was removed end to end: the view and template, the `Contact.offer_default_newsletters_condition` / `add_default_newsletters` methods (and the `import_module` they used), the four redirects in `core/admin.py` (plus the `response_add_or_change_next_url` helper), the call in `invoicing/api.py`, and the `CORE_DEFAULT_NEWSLETTERS` setting. The CMS now applies its own default newsletters when it creates the account.

### 5. Newsletter maps retired and the inbound `update_customer` branch neutralized

**Files:** `settings.py`, `migration_settings.py`, `core/models.py`

`WEB_UPDATE_NEWSLETTER_MAP` and `WEB_UPDATE_AREA_NEWSLETTER_MAP` were removed (they were only used by the CSV producer and by `update_customer`). Because `update_customer` (the CMS→CRM receiver) read those maps dynamically, that branch was neutralized so it ignores the inbound `newsletters` / `area_newsletters[_remove]` fields.

### 6. Read/delta endpoint settings

**File:** `settings.py`

`WEB_NEWSLETTERS_READ_URI` and `WEB_NEWSLETTERS_UPDATE_URI` were added (default `None`, auto-derived from `LDSOCIAL_URL`). They are POSTs that must work regardless of `WEB_CREATE_USER_ENABLED` (they never create web users), so they are added to `WEB_CREATE_USER_POST_WHITELIST`.

### 7. Tests

**Files:** `tests/test_newsletters_proxy.py` (new), `tests/test_contact.py`

`test_newsletters_proxy.py` covers the three proxy views with the CMS mocked (8 tests). `test_contact.py` was adjusted to the removed default-newsletter behaviour.

## 📁 Files Modified

- **`core/models.py`** — guard on `update_web_user_newsletters`; removed `offer_default_newsletters_condition` / `add_default_newsletters`; neutralized the `update_customer` newsletter branch
- **`core/admin.py`** — removed the four default-newsletter dialog redirects and the `response_add_or_change_next_url` helper
- **`invoicing/api.py`** — removed the default-newsletter dialog call
- **`settings.py`** — added `WEB_NEWSLETTERS_READ_URI` / `WEB_NEWSLETTERS_UPDATE_URI` / `WEB_UPDATE_USER_NEWSLETTERS_ENABLED` + whitelist; removed `CORE_DEFAULT_NEWSLETTERS`, `WEB_UPDATE_NEWSLETTER_MAP`, `WEB_UPDATE_AREA_NEWSLETTER_MAP`
- **`migration_settings.py`** — dropped the removed map settings
- **`support/views/newsletters.py`** — new proxy views (overview / form / toggle)
- **`support/views/__init__.py`** — export the new views
- **`support/urls.py`** — routes for the proxy views
- **`support/views/contacts.py`** — `ContactAdminFormWithNewsletters` reduced to a plain form
- **`support/views/all_views.py`** — removed `default_newsletters_dialog`
- **`support/templates/contact_detail/tabs/_overview.html`** — Newsletters card loads by htmx; mirror precompute removed
- **`support/templates/create_contact/tabs/_newsletters.html`** — tab loads by htmx
- **`support/templates/create_contact/create_contact.html`** — added the htmx `<script>`
- **`support/templates/seller_console.html`** — new Newsletters card
- **`tests/test_contact.py`** — adjusted to the new behaviour

## 📁 Files Created

- **`support/templates/contact_detail/htmx/_newsletters_htmx.html`** — read-only overview partial
- **`support/templates/create_contact/htmx/_newsletters_form_htmx.html`** — editable form partial
- **`support/templates/create_contact/htmx/_newsletter_item.html`** — single newsletter toggle item
- **`tests/test_newsletters_proxy.py`** — proxy view tests (CMS mocked)

## 🧪 Manual Testing

1. **Read and edit on demand (happy path):**
   - Open a contact detail whose person exists in the CMS → the Newsletters card loads its active newsletters from the CMS.
   - Open the edit-contact Newsletters tab → toggle one newsletter → confirm in the CMS `Subscriber` that **only that one** changed.
   - Save the contact → the CMS newsletters do **not** change (no destructive push).
   - **Verify:** reads reflect the CMS live; edits are single-newsletter deltas; saving the contact never overwrites the CMS.

2. **Seller console:**
   - Open the seller console on a contact linked to a CMS subscriber.
   - **Verify:** the Newsletters card (below "Web Reading") lists the active newsletters; it can be collapsed.

3. **CMS unreachable (edge case):**
   - Point the CMS URIs at an unreachable host (or stop the CMS) and open a contact detail / seller console.
   - **Verify:** the page renders normally; only the Newsletters card shows the "could not load newsletters from the CMS" alert; saving the contact still works.

4. **Person not in the CMS yet (edge case):**
   - Open a contact whose person has no web account.
   - **Verify:** the card shows "this contact does not exist on the web yet" instead of an error.

## 📝 Deployment Notes

- **No database migrations.** The `SubscriptionNewsletter` mirror is intentionally **left in place and frozen** (not removed in this change).
- **Deploy in the same window as the CMS branch** (`utopia-cms` / `utopia_cms_ladiaria`): the proxy calls new CMS endpoints (`usuarios/api/newsletters/`, `usuarios/api/newsletter_update/`).
- **Production config (critical):** set `WEB_UPDATE_USER_NEWSLETTERS_ENABLED = False` in the CRM config (`ss_conf`). If left `True`, every `Contact` save keeps pushing a destructive `.set()` to the CMS.
- On the CMS side, set `CRM_UPDATE_NEWSLETTERS_ENABLED = False` (turns off the now-unnecessary CMS→CRM push).
- The new URIs auto-derive from `LDSOCIAL_URL`; verify `LDSOCIAL_API_KEY` is a valid CMS key.
- Removed settings (`CORE_DEFAULT_NEWSLETTERS`, `WEB_UPDATE_NEWSLETTER_MAP`, `WEB_UPDATE_AREA_NEWSLETTER_MAP`) can be deleted from prod config (optional; they sit inert otherwise).
- Full sequence and the rsync timing rule: see `plans/desync-crm-cms/desmapeo-newsletters/PRE_DEPLOY_CHECKLIST.md`.

## 🎓 Design Decisions

- **Proxy in the CRM, not browser→CMS directly:** keeps the CMS API key server-side and gives the CRM front a single origin.
- **Delta (add/remove), never `.set()`:** edits from the CRM can no longer wipe newsletters the CRM doesn't know about — that was the root bug.
- **Mirror left frozen, not deleted:** the newsletter filter still depends on it; removing it (and the dead push machinery) is a later cleanup phase, after the filter repopulation command exists.

## 🚀 Future Improvements

- Repopulation/reconciliation command (CMS→CRM by email) to restore the newsletter filter.
- Cleanup phase: remove the dead push (`update_web_user_newsletters`), its flag, and the signal callers after a prod bake.
- Extend the same htmx read pattern to any other views that show newsletters.

---

- **Date:** 2026-06-29
- **Author:** Tanya Tree + Claude Opus 4.8
- **Branch:** desmapeo-newsletters (t1158)
- **Type:** Refactor
- **Modules affected:** Core, Support, Invoicing, Settings
