# Deleting a subscription keeps its issues

- **Date:** 2026-11-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#192
- **Type:** Bug Fix
- **Component:** Support, Issues
- **Impact:** Data Integrity, Permissions

## 🎯 Summary

`Issue.subscription` was `on_delete=CASCADE`, so deleting a subscription deleted its issues, and with them their
activities (`Activity.issue` is also `CASCADE`). Issues and activities are the contact's history and should outlive
the subscription. The cascade also had a permissions side effect: Django's admin requires the delete permission on
every object the cascade would delete, so a user with `delete_subscription` still could not delete a subscription
that had issues unless they also had `delete_issue` and `delete_activity`. This was found when two users of a group
with limited admin permissions could not delete subscriptions.

This change makes `Issue.subscription` `SET_NULL`. Scheduled tasks and sales records keep their cascade on purpose.

## ✨ Changes

### 1. `Issue.subscription` is `SET_NULL`

**File:** `support/models.py`

```python
subscription = models.ForeignKey(
    "core.Subscription", verbose_name=_("Subscription"), on_delete=models.SET_NULL, null=True, blank=True
)
```

The field was already `null=True` and many issues have no subscription, so the code that reads
`issue.subscription` already handles `None`. Since the issue is no longer deleted, its activities stay too.

### 2. Migration

**File:** `support/migrations/0045_issue_subscription_set_null.py`

An `AlterField` that only changes `on_delete`. Django enforces `on_delete` in Python, not in the database, so the
migration does not alter the table.

## 📁 Files Modified

- **`support/models.py`**: `Issue.subscription` goes from `CASCADE` to `SET_NULL`
- **`CHANGELOG.md`**: entry for this change

## 📁 Files Created

- **`support/migrations/0045_issue_subscription_set_null.py`**: the migration
- **`tests/test_subscription_delete_keeps_issues.py`**: deleting a subscription keeps its issue (with no
  subscription) and the issue's activity, and still deletes its scheduled tasks and sales records

## 🧪 Manual Testing

1. **Happy path:**
   - Run `python -W ignore manage.py test --settings=test_settings --keepdb tests.test_subscription_delete_keeps_issues`
   - **Verify:** both tests pass
2. **From the admin, with a subscription that has an issue with activities:**
   - Open the subscription in the admin and click "Delete"
   - **Verify:** the confirmation page no longer lists the issue or its activities, and after deleting, the issue is
     still in the contact's detail with no subscription
3. **Edge case, a user without `delete_issue` nor `delete_activity`:**
   - Log in as a user with `delete_subscription` and the delete permission of the other related objects, but not
     those two, and delete a subscription that has issues
   - **Verify:** the admin lets them delete it

## 📝 Deployment Notes

- Migrations required: `python manage.py migrate`. It does not alter any table
- No configuration changes

## 🎓 Design Decisions

- **Scheduled tasks and sales records keep `CASCADE`:** without the subscription they mean nothing. A pending
  scheduled task left with no subscription would also fail every day in `run_scheduled_tasks`, because `execute()`
  writes to `self.subscription`. A sales record with no subscription would break the sales record filter and its
  exports, which read `sr.subscription.contact_id` and `sr.subscription.start_date`.
- **`Activity.issue` is not changed:** once the issue survives the subscription, its activities survive too.
  Deleting an issue directly still deletes its activities, as before.

---

- **Date:** 2026-11-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl192-incidencias-sin-cascada
- **Type:** Bug Fix
- **Modules affected:** Support
