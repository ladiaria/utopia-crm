from django.db import migrations
from django.db.models import Q


def migrate_countries_and_states(apps, schema_editor):
    Address = apps.get_model('core', 'Address')
    Country = apps.get_model('core', 'Country')
    State = apps.get_model('core', 'State')

    # First, create a default country (since we only have states)
    default_country, _ = Country.objects.get_or_create(
        name='Default',
        defaults={'code': 'DF'}
    )

    # Get unique states and create them
    unique_states = (
        Address.objects.exclude(Q(state__isnull=True) | Q(state=''))
        .values_list('state', flat=True)
        .distinct()
    )

    state_mapping = {}
    for state_name in unique_states:
        # Create a unique code by taking first 2 chars and adding a number if needed
        base_code = state_name[:2].upper()
        counter = 1
        code = base_code

        while True:
            existing = State.objects.filter(
                code=code,
                country=default_country
            ).exists()

            if not existing:
                break

            code = f"{base_code}{counter}"
            counter += 1

        state, created = State.objects.get_or_create(
            name=state_name,
            country=default_country,
            defaults={'code': code}
        )
        state_mapping[state_name] = state

    # Update addresses with new foreign keys
    for address in Address.objects.all():
        address.country_new = default_country

        if address.state:
            state = state_mapping.get(address.state)
            if state:
                address.state_new = state

        address.save()


def reverse_migrate(apps, schema_editor):
    # No need for reverse migration as we're keeping the old fields for now
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0075_address_country_new_address_state_new_and_more'),  # Replace with actual previous migration
    ]

    operations = [
        migrations.RunPython(migrate_countries_and_states, reverse_migrate),
    ]
