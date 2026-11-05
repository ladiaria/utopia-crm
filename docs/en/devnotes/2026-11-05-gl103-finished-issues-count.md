# The debtors CSV counts finished issues correctly

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#103
- **Type:** Bug Fix
- **Component:** Core Models, Support
- **Impact:** Reports

## 🎯 Summary

`Contact.get_finished_issues_by_category_count` had the same query as its open counterpart, so the "Finished invoicing issues" column of the debtors CSV showed the open ones, with the same number as the column next to it. It now counts the issues in a terminal status.

## ✨ Changes

### 1. The count

**File:** `core/models.py`

```python
return self.issue_set.filter(category=category, status__is_terminal=True).count()
```

### 2. The unused count goes away

**File:** `core/models.py`

`get_finished_issues_by_subcategory_count` had the same mistake and nothing used it, so it is removed instead of fixed.

## 📁 Files Modified

- **`core/models.py`** — Both counts
- **`tests/test_debtor_contacts.py`** — The counts and the CSV columns

## 🧪 Manual Testing

1. **Happy path:**
   - Export the debtors CSV for a debtor with open and closed invoicing issues.
   - **Verify:** Each column shows its own count.

2. **Edge case, another category:**
   - Close an issue of another category for the same contact.
   - **Verify:** It does not count in the finished column.

## 📝 Deployment Notes

No migrations required. The number in that column changes, so whoever uses that CSV should know.

---

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl103-contador-finalizadas
- **Type:** Bug Fix
- **Modules affected:** core, tests
