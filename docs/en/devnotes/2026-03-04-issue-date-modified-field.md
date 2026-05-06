# Issue Model: Added date_modified Field

**Date:** 2026-03-04
**Type:** Model Enhancement
**Component:** Issue Management
**Impact:** Data Tracking, Future Query Optimization

## Summary

Added a `date_modified` field to the `Issue` model to track when issues are last modified. This enables efficient detection of stale/inactive issues and provides a foundation for future modification-based filtering and reporting.

## Changes

### New Field: `date_modified`

```python
date_modified = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name=_("Date modified"))
```

- **`auto_now=True`**: Automatically updates on every `.save()` call
- **`null=True`**: Existing records are set to `NULL` (truthful — we don't know when they were last modified)
- Follows the same pattern as `ScheduledTask.modification_date`

### Migrations

1. **`support/migrations/0035_add_issue_date_modified.py`** — Adds the field to both `Issue` and `HistoricalIssue`
2. **`support/migrations/0036_reset_issue_date_modified_to_null.py`** — Data migration that resets all existing values to `NULL` (PostgreSQL fills the column with the current timestamp when adding an `auto_now` column, which is misleading for historical data)

## Design Decisions

### Why `NULL` for existing records?

When Django adds an `auto_now=True` column, PostgreSQL fills all existing rows with the migration timestamp. This would falsely imply all issues were "recently modified." The data migration resets these to `NULL`, which truthfully represents "modification date unknown."

### Why `DateTimeField` instead of `DateField`?

Using `DateTimeField` (vs `DateField` used by `date_created`) provides more granularity for future queries and is consistent with Django's `auto_now` best practices.

## Files Modified

- `support/models.py` — Added `date_modified` field to `Issue` model
- `support/migrations/0035_add_issue_date_modified.py` — Schema migration
- `support/migrations/0036_reset_issue_date_modified_to_null.py` — Data migration

## Deployment Notes

- Run `python manage.py migrate support` to apply both migrations
- The data migration resets ~523K existing issues to `NULL` (fast bulk update)
- No application restart required beyond the migration
- Going forward, every issue save will automatically populate `date_modified`
