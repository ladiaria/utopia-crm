from django.db import migrations
from django.db.models import Q


def migrate_countries_and_states(apps, schema_editor):
    Address = apps.get_model('core', 'Address')
    Country = apps.get_model('core', 'Country')
    State = apps.get_model('core', 'State')

    # Get unique countries and create them
    unique_countries = (
        Address.objects.exclude(Q(country__isnull=True) | Q(country='')).values_list('country', flat=True).distinct()
    )

    country_mapping = {}
    for country_name in unique_countries:
        country, created = Country.objects.get_or_create(
            name=country_name, defaults={'code': country_name[:2].upper()}  # Temporary code
        )
        country_mapping[country_name] = country

    # Create states for each country
    state_mapping = {}
    for country_name, country in country_mapping.items():
        states = (
            Address.objects.filter(country=country_name)
            .exclude(Q(state__isnull=True) | Q(state=''))
            .values_list('state', flat=True)
            .distinct()
        )

        for state_name in states:
            state, created = State.objects.get_or_create(
                name=state_name, country=country, defaults={'code': state_name[:10]}  # Temporary code
            )
            state_mapping[f"{country_name}:{state_name}"] = state

    # Update addresses with new foreign keys
    for address in Address.objects.all():
        if address.country:
            country = country_mapping.get(address.country)
            if country:
                address.country_new = country

                if address.state:
                    state = state_mapping.get(f"{address.country}:{address.state}")
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
