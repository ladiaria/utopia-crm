# Error Reporting Infrastructure: Logging and Sentry Support

- **Date:** 2026-06-16
- **Author:** Tanya Tree + Claude Opus 4.8
- **Ticket:** t1156
- **Type:** Enhancement
- **Component:** Settings, Logging, Error Reporting
- **Impact:** Observability, Operability

## 🎯 Summary

When a MercadoPago subscription failed from the web, the real cause of the exception was lost in production (`DEBUG=False`), forcing the team to guess what went wrong. This ticket builds the base-app infrastructure to stop flying blind: a Django `LOGGING` configuration that preserves Django's default behaviour (email uncaught errors to `ADMINS`, plus stderr output captured by uWSGI), the `sentry-sdk` dependency, and documentation for initializing Sentry in production only. The MercadoPago-specific capture logic lives in `utopia-crm-ladiaria`; this base-app change provides the plumbing those reports rely on (`ADMINS`, the Sentry SDK, and the recipients setting default).

## ✨ Changes

### 1. Logging configuration in base settings

**File:** `settings.py`

A `LOGGING` dict was added that keeps Django's default behaviour and adds explicit console output:

- A `mail_admins` handler (Django's `AdminEmailHandler`) filtered by `require_debug_false`, so uncaught errors email the `ADMINS` only in production.
- A `console` (stderr) handler attached to the root and `django` loggers, so uWSGI captures everything in its log.
- No file handlers, by design.

`ADMINS` and `MANAGERS` were also given empty defaults so they can be populated per environment in `local_settings.py`.

### 2. Sentry SDK dependency

**File:** `requirements.txt`

`sentry-sdk` was added to the requirements. The actual initialization is **not** in base settings: it is done in `local_settings.py` so that only the environments that need it (production) enable Sentry.

### 3. Documentation of new settings

**File:** `local_settings_sample.py`

A commented reference block was added documenting:

- `ADMINS` / `MANAGERS`.
- `SENTRY_ENABLED`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT` and a full `sentry_sdk.init(...)` example guarded by `SENTRY_ENVIRONMENT == "production"`, with a `before_send` hook that filters sensitive MercadoPago / auth keys.
- `MERCADOPAGO_ERRORS_RECIPIENTS` (already used by debit errors) and the new `MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS`.

The `MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS` default (empty list) was also added to base settings next to the MercadoPago config.

## 📁 Files Modified

- **`settings.py`** — Added `LOGGING`, `ADMINS`/`MANAGERS` defaults, and `MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS` default
- **`requirements.txt`** — Added `sentry-sdk`
- **`local_settings_sample.py`** — Documented Sentry init, `ADMINS`, and the MercadoPago error recipients

## 📚 Technical Details

Sentry is initialized in `local_settings.py` rather than base settings on purpose: the base CRM app must stay deployable without a Sentry account, and only production should report. The init reads `SENTRY_ENABLED`, `SENTRY_DSN`, and `SENTRY_ENVIRONMENT`, and only calls `sentry_sdk.init` when the environment is `"production"`. The `before_send` hook strips sensitive keys (`token`, `security_code`, `mp_card_id`, `card_number`, etc.) from the request data before events are sent.

## 🧪 Manual Testing

1. **Uncaught error emails ADMINS in production:**
   - Set `DEBUG = False` and populate `ADMINS` in `local_settings.py`.
   - Trigger a 500 error on any view.
   - **Verify:** an error email is sent to the configured `ADMINS`, and the traceback appears in the uWSGI log.

2. **Edge case — no ADMINS configured:**
   - Leave `ADMINS = []` (base default).
   - Trigger a 500 error.
   - **Verify:** no email is attempted and no exception is raised by the logging handler; the error still appears on stderr / uWSGI log.

3. **Edge case — Sentry disabled in non-production:**
   - Set `SENTRY_ENVIRONMENT = "test"` (or leave `SENTRY_ENABLED` unset).
   - Start the app.
   - **Verify:** `sentry_sdk.init` is not called and the app boots normally.

## 📝 Deployment Notes

- Install the new dependency: `pip install -r requirements.txt` (adds `sentry-sdk`).
- No database migrations required.
- Per environment, configure in `local_settings.py`: `ADMINS`, and (production only) the Sentry block plus `MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS`.
- A dedicated Sentry project/DSN for the CRM should be created; the DSN goes in production `local_settings.py`.

## 🚀 Future Improvements

- Consider a `LOGGING` review to add named loggers for the billing and MercadoPago flows specifically.
- Optionally wire `release` tracking in Sentry via a `GIT_COMMIT` environment variable, as the CMS does.

---

- **Date:** 2026-06-16
- **Author:** Tanya Tree + Claude Opus 4.8
- **Branch:** t1156
- **Type:** Enhancement
- **Modules affected:** Settings, Logging, Error Reporting
