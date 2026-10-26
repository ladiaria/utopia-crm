# Logistics issues are blocked while a "not delivered" issue is open

- **Date:** 2026-10-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl61-logistica-no-entregado-abierto
- **Type:** Enhancement
- **Component:** Support (new issue form)
- **Impact:** Business logic, UI

## 🎯 Summary

When a subscription is moved to a special route (`SPECIAL_ROUTES_FOR_SELLERS_LIST`), the base creates a service issue
of the `ISSUE_SUBCATEGORY_NOT_DELIVERED` subcategory (`logistics/utils.py`). While that issue is open the paper is not
delivered on purpose, so a logistics issue such as "did not arrive" makes no sense, but nothing stopped an agent from
creating one. With the new setting `ISSUE_BLOCK_LOGISTICS_IF_NOT_DELIVERED_OPEN` enabled, the new issue page warns
beforehand and disables the submit button, and the form refuses the issue if it is posted anyway. Requested by la
diaria's call center (it/utopia-crm-ladiaria#61).

## ✨ Changes

### 1. `ISSUE_BLOCK_LOGISTICS_IF_NOT_DELIVERED_OPEN` setting

**Files:** `settings.py`, `local_settings_sample.py`

Defaults to `False`: without it, creating issues behaves exactly as before.

### 2. `get_blocking_not_delivered_issue(contact, category)`

**File:** `support/forms.py`

Returns the open not-delivered issue that blocks a new issue, or `None`. It only looks when the setting is on and the
category is logistics (`L`). The check is per **contact**, not per subscription: any open service (`S`) issue of the
`ISSUE_SUBCATEGORY_NOT_DELIVERED` subcategory blocks. "Open" means its status is not in `ISSUE_STATUS_FINISHED_LIST`,
so an issue with no status counts as open, as in `Contact.has_no_open_issues()`.

```python
contact.issue_set.filter(category="S", sub_category__slug=settings.ISSUE_SUBCATEGORY_NOT_DELIVERED)
    .exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
```

### 3. Preventive warning and disabled submit button

**Files:** `support/views/all_views.py`, `support/templates/new_issue.html`

`NewIssueView` puts the blocking issue in the context as `blocking_issue`. The template shows an `alert-warning` at
the top of the form, with a link to that issue, and renders the submit button `disabled`.

### 4. The form's `clean()` refuses it

**File:** `support/forms.py`

The disabled button is only a convenience: removing the attribute from the browser's inspector would post the form.
`IssueStartForm.clean()` runs the same check and raises a non-field error, which the existing error alert at the top
of the form shows. Since it is a regular form error, the page is re-rendered with everything the agent typed.

The check uses the contact in the form's `initial` (set by the view from the URL), not the hidden `contact` field:
the view saves the issue for the URL's contact, so editing the hidden field must not skip the check.

## 📁 Files Modified

- **`settings.py`** — New setting, `False` by default.
- **`local_settings_sample.py`** — The setting, commented out, with its explanation.
- **`support/forms.py`** — `get_blocking_not_delivered_issue()` and the check in `IssueStartForm.clean()`.
- **`support/views/all_views.py`** — `blocking_issue` in `NewIssueView`'s context.
- **`support/templates/new_issue.html`** — Warning and disabled submit button.
- **`locale/es/LC_MESSAGES/django.po`** — Spanish for the error and the warning.
- **`CHANGELOG.md`** — Entry for this change.

## 📁 Files Created

- **`tests/test_new_issue_not_delivered_block.py`** — 9 tests: open, closed and status-less not-delivered issues;
  other categories; setting off; tampered contact field; the warning and the disabled button on GET; a blocked POST
  that creates nothing and keeps the typed notes; and the button enabled when nothing blocks.

## 🎓 Design Decisions

- **In the base, not in a customization package.** The base creates the not-delivered issue and owns the new issue
  form, so the rule is coherent here. The setting keeps it opt-in for other installations.
- **A form error instead of AJAX.** Validating on submit already keeps the typed data and shows the error where the
  form shows the others; an AJAX check would add code for no visible gain, since the warning already appears when
  the page loads.
- **Per contact, not per selected subscription.** A contact on hold for delivery should not get logistics issues on
  any of their subscriptions.

## 🧪 Manual Testing

1. **Contact with an open not-delivered issue (happy path):**
   - Enable the setting. Move a subscription to a special route so the service issue is created, or create a
     service issue with the not-delivered subcategory by hand.
   - Open "New issue" for that contact.
   - **Verify:** the yellow warning with a link to the issue, and the "Create Issue" button disabled.

2. **Bypassing the disabled button:**
   - On the same page, remove `disabled` from the button with the browser's inspector, fill in the form and submit.
   - **Verify:** the red error alert, the form still holds what was typed, and no issue is created.

3. **Not-delivered issue closed:**
   - Close the not-delivered issue and reload the page.
   - **Verify:** no warning, the button is enabled and the logistics issue is created.

4. **Setting off:**
   - With the setting off and the not-delivered issue open, open the page.
   - **Verify:** everything works as before.

## 📝 Deployment Notes

- No database migrations required.
- Compile translations: `python manage.py compilemessages -l es`.
- Enable `ISSUE_BLOCK_LOGISTICS_IF_NOT_DELIVERED_OPEN = True` in `local_settings.py` where the rule is wanted, and
  check that `ISSUE_SUBCATEGORY_NOT_DELIVERED` matches the installation's slug.

---

- **Date:** 2026-10-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl61-logistica-no-entregado-abierto
- **Type:** Enhancement
- **Modules affected:** Support
