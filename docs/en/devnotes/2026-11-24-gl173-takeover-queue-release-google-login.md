# Email takeover queue: release the Google login instead of sending the case to IT

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#173
- **Type:** Feature
- **Component:** core, support (email takeover queue)
- **Impact:** Call center, supervisors

## 🎯 Summary

When an operator gives a contact an address that, on the web, is only the Google login (`UserSocialAuth.uid`) of another account registered under a different address, the CMS answered `social_auth_conflict`. That reason is in `BLOCKING_PREVIEW_REASONS`, so the contact save stopped with «avisá a tu supervisor para que lo derive a soporte web» and IT removed the Google login by hand. It is almost always the same person: the account's email changed and the Google login kept the old address (contact 2631, 2026-11-24). The CMS now answers that case with a new takeover mode, `release_social_auth`: approving removes that Google login and frees the address, with no account deleted. On the CRM side the request goes to the queue like any other, and the queue shows which accounts lose their Google login.

## ✨ Changes

### 1. The queue shows the new mode

**File:** `support/templates/email_takeovers/queue.html`

- A `badge-warning` «Removes a Google login» for requests whose preview mode is `release_social_auth`.
- A «Loses its Google login» row listing each account from `released_social_auth`: its email, subscriber, a link to its contact when it has one, and an «Active subscription» badge. Below it, a short explanation for the reviewer: it is usually the same person, and no account is deleted.

### 2. `EmailTakeoverRequest.released_social_auth`

**File:** `core/models.py`

A property that reads `released_social_auth` from the stored preview, the same way `released_contact_id` does. The `takeover_mode` docstring lists the new mode. `deletes_an_account` stays `False` for it.

### 3. `social_auth_conflict` stays blocking

**File:** `core/email_takeover_queue.py`

It stays in `BLOCKING_PREVIEW_REASONS`, with a comment: only a CMS without the change sends it. That keeps the CRM safe if it is deployed before the CMS.

## 📁 Modified Files

- **`support/templates/email_takeovers/queue.html`** — Badge and «Loses its Google login» row
- **`core/models.py`** — `EmailTakeoverRequest.released_social_auth`; `takeover_mode` docstring
- **`core/email_takeover_queue.py`** — Comment on `social_auth_conflict` in `BLOCKING_PREVIEW_REASONS`
- **`locale/es/LC_MESSAGES/django.po`** — The four new strings, added by hand: `makemessages` brings in thousands of lines from other pending changes
- **`tests/test_email_takeover_views.py`** — The queue shows the account that loses its Google login and links its contact
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

1. **Normal case:** in the CMS, give account A (email `a@…`) a Google login with uid `b@…`, and make sure no account has `b@…` as email or username. In the CRM, change a contact's email to `b@…` from the contact edit screen. **Check:** the request reaches the queue with the «Removes a Google login» badge and lists account A. Approve it. **Check:** the contact has `b@…`, account A still exists without that Google login, and its own web account has `b@…`.
2. **Edge case, staff:** same as above with account A marked staff. **Check:** the contact save shows the staff message and nothing reaches the queue.
3. **Edge case, subscribed holder:** account A has an active subscription. **Check:** the queue shows the «Active subscription» badge next to it.

## 📝 Deployment Notes

- No migrations, no settings.
- Merge the CMS change first (`utopia_cms_ladiaria`, branch `gl173-soltar-google-trancado`). Without it, the CMS keeps answering `social_auth_conflict` and the CRM keeps blocking, as before.
- MercadoPago and Witty run the takeover on their own (no queue), so with the CMS change they release the Google login automatically too.

## 🎓 Design Decisions

- **Release the login, don't absorb the account.** The account holding the uid may belong to someone else, and absorbing it deletes an account, which cannot be undone. Removing the login only takes away the Google button: the account, its subscription and its data stay. If it was the same person, the next Google sign-in finds the contact's account by email (`associate_by_email`) and links it there.
- **Through the queue, not automatic.** A typo could free someone else's Google address for this contact. The reviewer sees which account loses the login, and whether it is subscribed, before approving.

---

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl173-soltar-google-trancado
- **Type:** Feature
- **Modules affected:** core, support
