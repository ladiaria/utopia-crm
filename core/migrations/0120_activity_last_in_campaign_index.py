from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Composite index matching "the latest activity of a (contact, campaign) pair", i.e. an
    ORDER BY -datetime, -id LIMIT 1 correlated subquery.

    Kept in its own migration on purpose: with atomic = False, if this index failed while sharing a
    migration with the previous one, the already created index would make the retry fail with
    "index already exists".
    """

    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    atomic = False

    dependencies = [
        ("core", "0119_activity_datetime_index"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="activity",
            index=models.Index(
                fields=["contact", "campaign", "-datetime", "-id"],
                name="core_act_cont_camp_dt_idx",
            ),
        ),
    ]
