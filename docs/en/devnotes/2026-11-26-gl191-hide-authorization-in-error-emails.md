# Hide the Authorization header in error emails

- **Date:** 2026-11-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#191
- **Type:** Security
- **Component:** Settings
- **Impact:** Error reporting

## 🎯 Summary

Django emails every uncaught exception to `ADMINS`, with the request's `META` included. Its default filter,
`SafeExceptionReporterFilter`, hides the keys that match `API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE`, but not
`HTTP_AUTHORIZATION`. That header carries the API key other systems use to call the CRM (`Authorization: Api-Key …`,
from `djangorestframework-api-key`) and any HTTP basic auth credentials, so every 500 on an API view sent them in
clear text to several mailboxes. It was found in a 500 email from utopia-cms, which has the same problem and gets the
same fix.

This change sets `DEFAULT_EXCEPTION_REPORTER_FILTER` to a subclass that also hides `AUTHORIZATION`.

## ✨ Changes

### 1. The filter

**File:** `util/error_reporting.py`

```python
class SafeExceptionReporterFilter(DjangoSafeExceptionReporterFilter):
    hidden_settings = re.compile("API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|AUTHORIZATION", flags=re.I)
```

Django's pattern plus `AUTHORIZATION`. Django applies the same pattern to settings and to `request.META`, so the
header is replaced by `********************` and the rest of the request is reported as before.

### 2. The setting

**File:** `settings.py`

`DEFAULT_EXCEPTION_REPORTER_FILTER = "util.error_reporting.SafeExceptionReporterFilter"`, next to `ADMINS`. It is
set before `from local_settings import *`, so it applies to every installation and a `local_settings.py` can still
override it.

## 📁 Files Modified

- **`settings.py`**: `DEFAULT_EXCEPTION_REPORTER_FILTER`
- **`CHANGELOG.md`**: entry for this change

## 📁 Files Created

- **`util/error_reporting.py`**: the filter
- **`tests/test_error_reporting.py`**: the header is hidden in `META` and in the email text, and the rest of the
  request is still reported. Without the setting, both tests fail

## 🧪 Manual Testing

1. **Happy path:**
   - Run `python -W ignore manage.py test --settings=test_settings --keepdb tests.test_error_reporting`
   - **Verify:** both tests pass
2. **Edge case:**
   - Comment out `DEFAULT_EXCEPTION_REPORTER_FILTER` in `settings.py` and run the tests again
   - **Verify:** both fail, because Django's own filter leaves `HTTP_AUTHORIZATION` in clear text
3. **In an environment that sends error emails:**
   - Call an API view with an API key and make it fail
   - **Verify:** the email shows `HTTP_AUTHORIZATION` as `********************`

## 📝 Deployment Notes

- No migrations
- No changes in `local_settings.py`
- Restart the application server, as with any settings change. The filter applies from that moment: emails
  already sent keep the key

## 🎓 Design Decisions

- **In the base `settings.py`, not in each deployment's `local_settings.py`:** the leak happens in any installation
  that has API keys and `ADMINS`, so the fix belongs to the base.
- **The setting and not `@sensitive_variables` or `@sensitive_post_parameters`:** those protect local variables and
  POST parameters of one view. The header is in `META`, and it reaches every view.

---

- **Date:** 2026-11-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl191-ocultar-authorization-en-errores
- **Type:** Security
- **Modules affected:** settings, util
