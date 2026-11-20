# Remove the `es_CO` locale and three unused subscription fields

- **Date:** 2026-11-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#91
- **Type:** Refactor
- **Component:** Core Models, Translations
- **Impact:** Database schema (three columns dropped), translations

## 🎯 Summary

A deployment that no longer uses the CRM left behind a locale and three `Subscription` fields that only its own customization package used. `locale/es_CO/` (2,312 strings) was not in `LANGUAGES`, but `makemessages -a` kept updating it, so every translation change dragged it into the diff. `purchase_date` was shown in the admin but nobody edited it, so it repeated the day of `creation_date`. `zoho_synced` and `zoho_sync_date` were only read and written by that package's Zoho sync. This change deletes the locale and drops the three fields.

## ✨ Changes

### 1. `locale/es_CO/` deleted

**File:** `locale/es_CO/LC_MESSAGES/django.po`

`LANGUAGES` is `en` and `es`, and `LANGUAGE_CODE` is `es`, so nothing loaded it. From now on, update translations with `makemessages -l es` instead of `-a`: `-a` only regenerates the locales that already exist, so `es_CO` does not come back, but `-l es` makes the intent explicit. `compilemessages` (with or without `-l es`) needs no change.

### 2. `Subscription.purchase_date`, `zoho_synced` and `zoho_sync_date` dropped

**Files:** `core/models.py`, `core/admin.py`, `core/migrations/0128_remove_subscription_cambio_fields.py`

- The three fields are removed from `Subscription`, and the `purchase_date` line goes from the subscription admin fieldset.
- Migration `core.0128` drops the three columns from `core_subscription` and from `core_historicalsubscription`.
- For the date a subscription was sold, use `creation_date`.

## 📁 Files Modified

- **`core/models.py`** — Removed `purchase_date`, `zoho_synced` and `zoho_sync_date` from `Subscription`
- **`core/admin.py`** — Removed `purchase_date` from the subscription fieldset
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`core/migrations/0128_remove_subscription_cambio_fields.py`** — Drops the three columns from `Subscription` and `HistoricalSubscription`

## 📁 Files Deleted

- **`locale/es_CO/LC_MESSAGES/django.po`** — The unused Colombian Spanish locale

## 📚 Technical Details

- The fields came in with `core.0091` (`purchase_date`, 2025-01-31) and `core.0092` (the Zoho fields, 2025-02-27). Those migrations stay: removing them would break the migration history of every existing database.
- Before deleting, the whole `~/git` tree (base, la diaria's package, rponline, the CMS repos and the docs) was searched for `purchase_date`, `zoho_synced`, `zoho_sync_date`, `es_CO` and `es-co`. Outside this repo they only appear in old clones of the deployment that no longer uses the CRM.
- At la diaria, `purchase_date` matched the day of `creation_date` in all 3,456 Normal and Promotion subscriptions from August to October 2026, so no information is lost.
- Dropping a column is not reversible with its data: `migrate core 0127` recreates the columns empty (with their defaults).

## 🧪 Manual Testing

1. **Subscription admin:** open a subscription in the admin. **Verify:** it loads, and the last row of the fieldset only shows the renewal type.
2. **New subscription:** create a subscription from a contact (or with the seller console). **Verify:** it saves, and its history shows no error.
3. **Translations:** with the language in Spanish, open any CRM page. **Verify:** texts are still in Spanish (the `es` locale is untouched).

## 📝 Deployment Notes

- **Migration required, right after the merge:** `python manage.py migrate`. Until it runs, **saving any subscription fails**. `zoho_synced` is `NOT NULL` with no database default (Django keeps the default in Python only), the new code no longer sends it, and every save also inserts a `HistoricalSubscription` row. The window is the time between the deploy hook and the `migrate`. Merge when few people are working, and outside the nightly maintenance window, which creates and updates subscriptions.
- Other deployments: if a customization package reads or writes any of the three fields, or has `es-co` in `LANGUAGES`, it must stop before updating.

---

- **Date:** 2026-11-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl18-gl91-codigo-muerto
- **Type:** Refactor
- **Modules affected:** Core, Translations
