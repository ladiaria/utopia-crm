# Foreign phone numbers show their country

- **Date:** 2026-10-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl19-pais-telefonos
- **Type:** Enhancement
- **Component:** Core (template tags), Support (contact detail, seller console, issues)
- **Impact:** UI

## 🎯 Summary

The contact detail always showed `phone` and `mobile` in national format (`as_national`), whatever their country. A
local mobile reads fine, but a foreign one loses its country code: `+5491123456789` was shown as `011 15-2345-6789`,
and whoever read it had no way to know it was Argentine. The same happened with the SIP call button, which dialed the
national format, so it called a foreign number as if it were a local one. Foreign numbers were rare until la diaria's
book purchase started accepting mobiles from any country (it/utopia-crm-ladiaria#15). Now numbers from outside
`PHONENUMBER_DEFAULT_REGION` are shown in international format with their country flag, and get no call button,
because the call center doesn't dial abroad.

## ✨ Changes

### 1. `phone_display` filter

**File:** `core/templatetags/core_tags.py`

A new filter that keeps the national format for local numbers and shows the rest in international format, followed by
the flag:

```html
{{ contact.mobile|phone_display }}
<!-- +54 9 11 2345-6789 <span class="flag-icon flag-icon-ar" title="AR"></span> -->
```

The local country is not hardcoded: it comes from `PHONENUMBER_DEFAULT_REGION`. The decision lives in a plain helper,
`foreign_region(value)`, which returns the region code of a valid foreign number and `None` for anything else (local,
invalid or empty numbers, and plain strings), so the SIP filter can reuse it.

The contact detail tabs (`_overview.html` and `_information.html`) use the filter for `phone` and `mobile` instead of
`as_national`.

### 2. No SIP call button for foreign numbers

**File:** `core/templatetags/sip_tags.py`

The `sip` filter returns `phone_display` (number and flag, no button) when `foreign_region` finds a foreign country.
This covers every template that uses it: the seller console, the special routes console and the issue view. Local
numbers, invalid numbers and plain strings (`work_phone` is a `CharField`) keep the button as before.

### 3. Flags available on every page

**File:** `templates/adminlte/lib/_styles.html`

`flag-icon-css` was already bundled with AdminLTE (`static/admin-lte/plugins/flag-icon-css/`) but not loaded. It is
now loaded with the global styles, since the flags show up in the contact detail, the seller console and the issue
view. The stylesheet only fetches the SVG of the flags actually shown.

## 📁 Files Modified

- **`core/templatetags/core_tags.py`** — `foreign_region` helper and `phone_display` filter.
- **`core/templatetags/sip_tags.py`** — `sip` filter without the button for foreign numbers.
- **`support/templates/contact_detail/tabs/_overview.html`** — `phone` and `mobile` through `phone_display`.
- **`support/templates/contact_detail/tabs/_information.html`** — Same as the overview.
- **`templates/adminlte/lib/_styles.html`** — Loads `flag-icon-css`.
- **`CHANGELOG.md`** — Entry for this change.

## 📁 Files Created

- **`tests/test_phone_display.py`** — Tests for `phone_display` (local, foreign, empty and invalid numbers) and for
  the `sip` filter (button for local numbers and plain strings, no button for foreign numbers).

## 🎓 Design Decisions

- **International format, not only the flag.** With the flag next to `011 15-2345-6789`, the number still reads as a
  local one and cannot be dialed as shown. The international format carries the country code.
- **Flag instead of the country name.** The project installs `phonenumberslite`, which has no geocoder data, so the
  country name is not available without a new dependency. The flag comes from a library that was already bundled;
  hovering shows the region code.
- **Invalid numbers keep their current behaviour.** Without a valid number there is no reliable country, so they are
  shown in national format and keep the call button, as before.
- **No call button for foreign numbers instead of dialing them in international format.** The call center doesn't
  dial abroad.

## 🧪 Manual Testing

1. **Contact with a foreign mobile (happy path):**
   - Open the detail of a contact whose mobile is foreign (e.g. `+5521…`, Brazil) and whose phone is local.
   - **Verify:** in the overview and the Information tab, the phone looks as before and the mobile shows as
     `+55 21 …` followed by the Brazilian flag.

2. **Issue or seller console with a foreign number:**
   - Open an issue (or the seller console) of a contact with a foreign mobile.
   - **Verify:** the foreign mobile shows with its flag and without the "Llamar" button; a local number still has it.

3. **Number the system doesn't recognize (edge case):**
   - Open a contact whose number was stored without a valid format (e.g. a foreign number without `+`).
   - **Verify:** it is shown as before, without a flag, and keeps the call button.

4. **Automated tests:**

   ```bash
   python -W ignore manage.py test --settings=test_settings --keepdb tests.test_phone_display
   ```

   - **Verify:** 7 tests OK.

## 📝 Deployment Notes

- No database migrations required.
- No translations to compile.
- No configuration changes: the local country is the existing `PHONENUMBER_DEFAULT_REGION`.
- Run `collectstatic` as in any deploy: `flag-icon-css` was already in `static/`.

---

- **Date:** 2026-10-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl19-pais-telefonos
- **Type:** Enhancement
- **Modules affected:** Core, Support
