# HTML emails go through Django's email backend

- **Date:** 2026-11-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#162
- **Type:** Bug Fix
- **Component:** util (mailer)
- **Impact:** Notifications

## 🎯 Summary

`util.mailer.send_html_email` built the message with `email.mime` and sent it with `smtplib`, straight to `EMAIL_HOST`. So it skipped `EMAIL_BACKEND` and everything a deployment configures there. At la diaria, the customization package sets a backend that adds a Reply-To to internal emails (it/utopia-crm-ladiaria#161), and the three notifications that use this function went out without it. Tests could not read these emails from `mail.outbox` either. The function now sends through Django, with the same signature.

## ✨ Changes

### 1. `send_html_email` uses `EmailMessage`

**File:** `util/mailer.py`

```python
message = EmailMessage(subject, render_to_string(template, context or {}), from_address, list(to_addresses))
message.content_subtype = "html"
return message.send()
```

- Same signature and the same rendered template; the body goes as a single `text/html` part (before, a multipart with one HTML part).
- It goes through `EMAIL_BACKEND`, with Django's SMTP settings (`EMAIL_HOST`, `EMAIL_PORT`, and TLS and authentication only if they are set). The old code always tried a login and ignored the failure when the server had no authentication.
- It still raises on SMTP errors, as before. It now returns the number of messages sent.
- The mutable default `context={}` became `context=None`.
- Django adds `Message-ID` and `Date` headers.

## 📁 Modified Files

- **`util/mailer.py`** — `send_html_email` through Django's email backend
- **`CHANGELOG.md`** — Entry for this change

## 📁 Created Files

- **`tests/test_mailer.py`** — The rendered template goes out as HTML, with its sender, recipients and subject; the context defaults to empty; a tuple of recipients works; and the email goes through the configured `EMAIL_BACKEND`

## 🧪 Manual Testing

1. **Normal case:** in a shell, `send_html_email(settings.DEFAULT_FROM_EMAIL, ["you@example.com"], "Test", "<an existing template>.html", {})`. **Check:** it returns `1`, the email arrives rendered as HTML, and it has the headers that `EMAIL_BACKEND` adds (at la diaria, the Reply-To to informática).
2. **Edge case:** with an unreachable `EMAIL_HOST`. **Check:** it raises, as before, so callers that catch errors keep working.

## 📝 Deployment Notes

- No migrations. No settings: it uses the email settings that are already there.

---

- **Date:** 2026-11-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl162-send-html-email-django
- **Type:** Bug Fix
- **Modules affected:** util
