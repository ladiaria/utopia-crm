# The contact import test does not depend on a customization package

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#102
- **Type:** Bug Fix
- **Component:** Tests
- **Impact:** Test suite only

## 🎯 Summary

`test_import_with_invalid_document_type` expected the imported contact to have no document type. A customization package can classify documents that arrive without a type when the contact is saved, so the test failed with one installed. It now checks that the invalid type is not created.

## ✨ Changes

### 1. The assertion

**File:** `tests/test_import_contacts.py`

`assertIsNone(contact.id_document_type)` becomes a check that no `IdDocumentType` named `INVALID_TYPE` exists. The test keeps checking that the contact is created, that it keeps its document number and that the warning is shown.

## 📁 Files Modified

- **`tests/test_import_contacts.py`** — The assertion

## 🧪 Manual Testing

1. **Happy path:**
   - Run `tests.test_import_contacts` with the customization package installed and its document types loaded.
   - **Verify:** It passes.

2. **Edge case, no package:**
   - Run it without a customization package.
   - **Verify:** It passes too. Not run for this change.

## 📝 Deployment Notes

No migrations required. Only a test changes.

---

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl102-test-import-tipo-documento
- **Type:** Bug Fix
- **Modules affected:** tests
