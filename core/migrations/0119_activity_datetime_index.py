from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Index on Activity.datetime, so that filtering activities by date range stops doing a sequential
    scan over the whole table.

    Built with CONCURRENTLY: a plain CREATE INDEX takes a ShareLock that blocks writes on
    core_activity while it builds, which on a busy install means stopping the call center.
    """

    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    atomic = False

    dependencies = [
        ("core", "0118_subscription_added_products"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="activity",
            index=models.Index(fields=["datetime"], name="core_activity_datetime_idx"),
        ),
    ]
