"""
Data migration to reset date_modified to NULL for all existing issues.

When the date_modified field was added with auto_now=True, PostgreSQL filled all
existing rows with the current timestamp. Since we don't actually know when these
issues were last modified, NULL is the truthful value for pre-existing records.

Going forward, any .save() call will correctly populate date_modified via auto_now.
"""

from django.db import migrations


def reset_date_modified(apps, schema_editor):
    """Set date_modified to NULL for all existing issues."""
    Issue = apps.get_model("support", "Issue")
    updated = Issue.objects.all().update(date_modified=None)
    print(f"\n  Reset date_modified to NULL for {updated} issues")


def noop(apps, schema_editor):
    """No reverse needed — auto_now will repopulate on next save."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("support", "0035_add_issue_date_modified"),
    ]

    operations = [
        migrations.RunPython(reset_date_modified, noop),
    ]
