# Removal of the dead CRM → CMS newsletters push

- **Date:** 2026-10-30
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl35-cleanup-desmapeo-nl
- **Type:** Refactor
- **Component:** Core (models, signals), settings
- **Impact:** CMS sync, extensions that imported the removed function

## 🎯 Summary

Since t1158 (in production at la diaria since 2026-06-30) the CMS is the source of truth for newsletters: the CRM
reads and edits them on demand by delta, and the old full push was switched off with
`WEB_UPDATE_USER_NEWSLETTERS_ENABLED = False`. That push, `update_web_user_newsletters`, sent the local mirror of the
contact's newsletters on every `Contact` save, and the CMS applied it with a `.set()`: a full replacement that wiped
the newsletters the CRM did not mirror. The flag was kept as a rollback kill switch while the change baked in
production. After four months without incidents, the function, its call from `contact_post_save_signal` and the flag
are removed (it/utopia-crm-ladiaria#35).

## ✨ Changes

### 1. The push function

**File:** `core/models.py`

`update_web_user_newsletters` is deleted, along with the `json` import that only it used. `get_newsletter_products`
stays: the newsletter mirror and la diaria's API still read it.

### 2. Its call on every `Contact` save

**File:** `core/signals.py`

`contact_post_save_signal` no longer calls it. The rest of the signal is unchanged: `update_web_user` keeps syncing
the contact's other fields to the CMS.

### 3. The flag

**File:** `settings.py`

`WEB_UPDATE_USER_NEWSLETTERS_ENABLED` is removed from the base settings. Nothing reads it anymore, so a deployment
that still sets it in `local_settings.py` is unaffected and can delete the line.

### 4. Stale extension point in `CLAUDE.md`

**File:** `CLAUDE.md`

The extension patterns listed `CORE_DEFAULT_NEWSLETTERS`, a setting that t1158 already removed from the code.

## 📁 Files Modified

- **`core/models.py`** — `update_web_user_newsletters` and the unused `json` import removed.
- **`core/signals.py`** — call and import removed from `contact_post_save_signal`.
- **`settings.py`** — `WEB_UPDATE_USER_NEWSLETTERS_ENABLED` removed.
- **`CLAUDE.md`** — `CORE_DEFAULT_NEWSLETTERS` removed from the extension patterns.

## 📚 Technical Details

**What stays.** `update_web_user` keeps its `newsletter_data` / `area_newsletters` parameters, and the
`SubscriptionNewsletter` mirror, its admin and the newsletter filter are untouched. They stay frozen until the
newsletters reconciliation, which repopulates the mirror from the CMS.

**Behaviour is unchanged where the flag was `False`.** The function returned early, so removing it changes nothing.
Where the flag was missing or `True` (its old default), every `Contact` save stops overwriting the CMS newsletters,
which is the intended model.

## 🧪 Manual Testing

1. **Saving a contact still syncs its fields:**
   - With `WEB_UPDATE_USER_ENABLED = True`, change the name of a contact linked to a CMS account and save.
   - **Verify:** the name changes in the CMS, and the CMS newsletters of that person stay as they were.

2. **Newsletters are still edited against the CMS:**
   - Open the newsletters of a contact in the CRM, add one and remove another.
   - **Verify:** both changes reach the CMS and no other newsletter of the person changes.

3. **Edge case — an old `local_settings.py` with the flag:**
   - Leave `WEB_UPDATE_USER_NEWSLETTERS_ENABLED = False` (or `True`) in `local_settings.py` and run
     `python manage.py check`.
   - **Verify:** no errors, and saving a contact does not send newsletters to the CMS in either case.

## 📝 Deployment Notes

- No database migrations required.
- A customization package that imports `update_web_user_newsletters` has to drop that import in the same deploy,
  or it fails on startup with an `ImportError`. At la diaria, `utopia-crm-ladiaria` goes together with this change.
- After deploying, `WEB_UPDATE_USER_NEWSLETTERS_ENABLED` can be deleted from `local_settings.py`.

---

- **Date:** 2026-10-30
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl35-cleanup-desmapeo-nl
- **Type:** Refactor
- **Modules affected:** Core, Settings
