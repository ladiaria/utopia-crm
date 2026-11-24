# Edit contact: the CMS email check runs once per save

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#177
- **Type:** Performance / Bug Fix
- **Component:** support (contact edit view)
- **Impact:** Anyone saving a contact from «Edit contact»

## 🎯 Summary

Saving a contact from «Edit contact» took about 6 seconds in production: in the uWSGI logs, the 98 `POST /support/contacts/<id>/edit/` of the previous days had a median of 5.6 s and a p90 of 6.7 s. About 5 s of that were two identical requests to the CMS `email_check` API, each taking about 2.5 s (measured in production on 2026-11-24).

`Contact.clean()` calls `custom_clean()`, which asks the CMS whether the email is free. It ran twice:

1. When the `ModelForm` validates, inside its `_post_clean()`.
2. When `Contact.save()` runs, because `save()` calls `clean()` unless `_skip_clean` is set.

`ContactUpdateView.form_valid` did set `_skip_clean`, but only around `form.save(False)`, which saves nothing. It removed the flag before `super().form_valid()`, where the real save happens, so `save()` ran the check again with the same data.

## ✨ Changes

### 1. The flag stays up during the real save

**File:** `support/views/contacts.py`

`form_valid` sets `_skip_clean`, calls `super().form_valid()` and removes the flag in a `finally`. This is the same pattern `ContactAdmin.save_model` already used. The `form.save(False)` call goes away: it saved nothing, and its `except` could not catch a failure of the real save.

### 2. The success message only after a successful save

**File:** `support/views/contacts.py`

«Contact saved successfully» was added before the real save, so it showed up even when the save failed and the form came back with an error. It is now added after `super().form_valid()` returns.

## 📁 Modified Files

- **`support/views/contacts.py`** — `ContactUpdateView.form_valid`
- **`tests/test_edit_contact_view.py`** — New: one email check per save, tags saved, a rejected email is not saved
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

1. **Normal case:** edit a contact's name and save. **Check:** the contact detail opens with «Contact saved successfully» and the new name.
2. **Edge case, email taken in the web:** change the email to one that another web account has. **Check:** the form comes back with the CMS's reason, nothing is saved, and there is no «Contact saved successfully».
3. **Production:** after the deploy, the median of `POST /support/contacts/<id>/edit/` in `/var/log/uwsgi/utopia-crm.log` drops by about 2.5 s.

## 📝 Deployment Notes

- No migrations, no settings.

## 🎓 Design Decisions

- **Why skipping the second check loses nothing:** both run on the same instance with the same data. Whatever the first one does (queue an email takeover, run the dedupe, reject the email) is already done when `save()` runs. When the takeover is queued, the first check even puts the old email back, so the second one only confirmed the email the contact already had.
- **`email_check` itself takes 2.5 s on the CMS side.** That is slow for a lookup by email, but it lives in the CMS and is out of scope here.

---

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl177-email-check-una-vez
- **Type:** Performance / Bug Fix
- **Modules affected:** support
