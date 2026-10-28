# The nightly invoicing issue auto-close closes again

- **Date:** 2026-10-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl63-close-invoicing-issues-subcategorias
- **Type:** Bug Fix
- **Component:** Support (`close_invoicing_issues` command)
- **Impact:** Data Integrity, Business logic

## 🎯 Summary

`close_invoicing_issues` closes the open invoicing issues of contacts that are no longer debtors. It filtered the
`ISSUE_SUBCATEGORY_AUTO_CLOSE_SLUGS` list against the issue's **status** instead of its subcategory, so with both
auto-close settings set the queryset was always empty and the command closed nothing. Fixing the filter alone was not
enough: a contact also stops being a debtor when their overdue invoices are marked as uncollectible, and those issues
would have been closed as "solved, invoices paid" without any payment. The command now looks at the contact's last
settled invoice: paid or debited closes the issue as solved, as before; uncollectible closes it with the status in the
new setting `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE`, or leaves it open without the setting. Found by la diaria
(it/utopia-crm-ladiaria#63).

## ✨ Changes

### 1. Subcategories filtered by subcategory

**File:** `support/management/commands/close_invoicing_issues.py`

```python
issues = issues.filter(sub_category__slug__in=issue_subcat_autoclose)  # was status__slug__in
```

### 2. Paid vs. uncollectible: the last settled invoice

**File:** `support/management/commands/close_invoicing_issues.py`

For a contact that is no longer a debtor (`Contact.is_debtor()`, which does not count uncollectible invoices),
`last_settled_invoice()` returns the last non-canceled invoice that is paid, debited or uncollectible:

- **Paid or debited:** `mark_solved()` with the same note as before.
- **Uncollectible:** with `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE` set, the issue gets that status, today's closing
  date and a note in `answer_2` saying the overdue invoices were marked as uncollectible. Without it, the issue is
  left open.
- **None:** the issue is left open.

A pending invoice that has not expired yet is skipped: it is a new billing cycle and says nothing about how the debt
of the issue ended.

### 3. `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE` setting

**Files:** `settings.py`, `local_settings_sample.py`

Defaults to `None`. It must be the slug of a finished status (e.g. `not-solved`).

### 4. `--dry-run`

**File:** `support/management/commands/close_invoicing_issues.py`

Prints what would be closed, and how, without saving. The first run after this fix may close at once everything that
piled up while the command did nothing.

### 5. Translations

**File:** `locale/es/LC_MESSAGES/django.po`

The messages are now translated with `gettext` and `.format()` outside the call (before, the formatted string was the
msgid, so it never matched). Two new strings in Spanish. The unused `DEFAULT_NOTE` was removed.

## 📁 Files Modified

- **`support/management/commands/close_invoicing_issues.py`** — Subcategory filter, last settled invoice, uncollectible
  closing, `--dry-run`.
- **`settings.py`** — `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE`, `None` by default.
- **`local_settings_sample.py`** — The setting, commented out, with its explanation.
- **`locale/es/LC_MESSAGES/django.po`** — Spanish for the new messages.
- **`CHANGELOG.md`** — Entry for this change.

## 📁 Files Created

- **`tests/test_close_invoicing_issues.py`** — 8 tests: paid, uncollectible with and without the setting, paid after
  old uncollectible debt, pending not expired, still a debtor, other subcategory or status, and `--dry-run`.

## 🎓 Design Decisions

- **The last settled invoice, not "has any uncollectible invoice".** A contact with uncollectible debt from years ago
  who later paid everything did pay: their issue is solved.
- **Uncollectible issues are closed, not reopened or left hanging.** Once the debt is written off nothing else can be
  done with the issue, so it counts as closed, but not as solved. The status is configurable because each
  installation names its statuses differently.
- **Opt-in for the uncollectible status.** Without the setting, an installation keeps the old intended behavior for
  payers and nothing new happens to written-off debt.

## 🧪 Manual Testing

1. **Contact that paid (happy path):**
   - Open invoicing issue in an auto-close status and subcategory; mark the contact's overdue invoice as paid without
     going through the payment flow that already closes issues.
   - Run `python manage.py close_invoicing_issues --dry-run`, then without the flag.
   - **Verify:** the dry run lists the issue as paid and changes nothing; the real run leaves it solved with the
     "cerrada automáticamente por pago de facturas" note.

2. **Written-off debt:**
   - Set `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE`. Mark the contact's overdue invoices as uncollectible.
   - Run the command.
   - **Verify:** the issue has that status, today's closing date and the uncollectible note.

3. **Written-off debt without the setting:**
   - Same as above with the setting unset.
   - **Verify:** the issue stays open.

4. **New cycle pending:**
   - The contact paid the issue's invoice and has a new invoice that expires next week.
   - **Verify:** the issue is closed as solved.

## 📝 Deployment Notes

- No database migrations required.
- Compile translations: `python manage.py compilemessages -l es`.
- Set `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE` in `local_settings.py` if written-off debt should be closed.
- Before the first cron run, run `python manage.py close_invoicing_issues --dry-run` and review how many issues it
  would close: the backlog of every day the command did nothing closes at once.

---

- **Date:** 2026-10-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl63-close-invoicing-issues-subcategorias
- **Type:** Bug Fix
- **Modules affected:** Support
