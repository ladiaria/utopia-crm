from django.core.management.base import BaseCommand
from core.models import Country


class Command(BaseCommand):
    help = 'Clean up country and state data with proper ISO codes'

    def handle(self, *args, **options):
        country_codes = {
            'Uruguay': 'UY',
            'Argentina': 'AR',
            'Colombia': 'CO',
            'Chile': 'CL',
            'Brazil': 'BR',
            'Peru': 'PE',
            'Bolivia': 'BO',
            'Ecuador': 'EC',
            'United States': 'US',
            'Canada': 'CA',
        }

        for country in Country.objects.all():
            if country.name in country_codes:
                country.code = country_codes[country.name]
                country.save()
                self.stdout.write(f'Updated country code for {country.name}')
