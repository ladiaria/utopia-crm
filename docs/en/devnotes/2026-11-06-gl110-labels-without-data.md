# Printing labels no longer fails when there is nothing to print

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#110
- **Type:** Bug Fix
- **Component:** Logistics
- **Impact:** User Experience

## 🎯 Summary

A day without labels answered a 500 (`IndexError: pop from empty list`) on every label screen. `SheetLayout.flush` restores a reportlab state that is only saved when the first label is requested, so without labels there was nothing to restore. The PDF now comes out with a page that says there is nothing to print.

## ✨ Changes

### 1. `flush` knows whether there were labels

**File:** `logistics/labels.py`

`iterator` sets `has_labels` when the first label is requested. Without labels, `flush` writes the message instead of restoring the state. Since every label screen goes through `flush`, none of them had to change, including those of a customization package.

## 📁 Files Modified

- **`logistics/labels.py`** — The fix
- **`locale/es/LC_MESSAGES/django.po`** — The message
- **`tests/test_csv_uploads.py`** — Its print labels tests no longer need to mock `Canvas`
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`tests/test_labels_without_data.py`** — The three sheet formats, the screens without labels, and a sheet with labels

## 🧪 Manual Testing

1. **Happy path:**
   - Print labels for a day that has them.
   - **Verify:** They come out as always, with no extra page with the message.

2. **Edge case, no labels:**
   - Upload to "Labels from CSV" a file with only the header row.
   - **Verify:** The PDF opens, with "No hay etiquetas para imprimir".

## 📝 Deployment Notes

No migrations.

## 🎓 Design Decisions

- **A page with the message, not a screen message:** it fixes every screen from one place. A screen message would mean changing each view that prints labels. On a label roll, the message takes one label.

---

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl110-etiquetas-sin-datos
- **Type:** Bug Fix
- **Modules affected:** logistics, locale, tests
