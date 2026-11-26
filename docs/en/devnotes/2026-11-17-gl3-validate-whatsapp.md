# A phone can also be validated by WhatsApp

- **Date:** 2026-11-17
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#3
- **Type:** Feature
- **Component:** Core (Contact)
- **Impact:** Data

## 🎯 Summary

If someone writes to us on WhatsApp, the number they write from is theirs. This change adds "WhatsApp" as a validation source for Phone and Mobile, and a method that validates the field holding exactly the number a message came from. Whoever receives the messages (at la diaria, the customization package) calls it.

## ✨ Changes

### 1. `PhoneValidationSource.WHATSAPP`

**Files:** `core/choices.py`, `core/migrations/0127_phone_validation_source_whatsapp.py`

### 2. `Contact.validate_phone_number(number, source, when=None, user=None)`

**File:** `core/models.py`

Normalizes the number (any format the phone fields take) and compares it in E.164 with Phone and Mobile. It validates the one that matches, with `mark_phone_validated()`. Returns the field, or `None` when none matches or the number was already validated at the same or a later date (it never moves the date back).

The comparison is exact on purpose: the caller lookup by phone accepts partial matches, and a partial match does not prove the number is the person's.

## 📁 Modified Files

- **`core/choices.py`** — `PhoneValidationSource.WHATSAPP`
- **`core/models.py`** — `validate_phone_number()`
- **`tests/test_phone_validation.py`** — Tests of the method
- **`CHANGELOG.md`** — Entry for this change

## 📁 Created Files

- **`core/migrations/0127_phone_validation_source_whatsapp.py`** — The new source choices

## 🧪 Manual Testing

1. **Normal case:** in a shell, `contact.validate_phone_number("099 123 456", PhoneValidationSource.WHATSAPP)` on a contact with that mobile. **Check:** returns `"mobile"` and the contact detail shows "Validated" with source WhatsApp.
2. **Edge case:** with a number the contact doesn't have, or part of it. **Check:** returns `None` and nothing changes.

## 📝 Deployment Notes

- **Migration:** `core.0127_phone_validation_source_whatsapp`. Only changes the field choices: no data is touched.

---

- **Date:** 2026-11-17
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl3-validar-whatsapp
- **Type:** Feature
- **Modules affected:** core
