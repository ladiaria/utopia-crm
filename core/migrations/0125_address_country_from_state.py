"""
Addresses created after 0076 had no country: none of the screens or integrations that create them sets it
(it/utopia-crm-ladiaria#122). From now on Address.save takes it from the state; this fills the existing ones the same
way, in a single query. Addresses without a state are left as they are.
"""

from django.db import migrations
from django.db.models import OuterRef, Subquery


def country_from_state(apps, schema_editor):
    Address = apps.get_model("core", "Address")
    State = apps.get_model("core", "State")
    Address.objects.filter(country__isnull=True, state__country__isnull=False).update(
        country_id=Subquery(State.objects.filter(pk=OuterRef("state_id")).values("country_id")[:1])
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0124_historicalsubscription_currency_and_more"),
    ]

    operations = [migrations.RunPython(country_from_state, migrations.RunPython.noop)]
