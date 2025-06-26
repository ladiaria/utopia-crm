from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Campaign


class Command(BaseCommand):
    help = 'Disables campaigns that have reached their end date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes to the database',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        verbosity = options.get('verbosity', 1)
        
        today = timezone.now().date()
        
        # Find campaigns that are active but have an end_date in the past
        expired_campaigns = Campaign.objects.filter(
            active=True,
            end_date__isnull=False,
            end_date__lt=today
        )
        
        count = expired_campaigns.count()
        
        if verbosity >= 1:
            self.stdout.write(f"Found {count} expired campaign(s) to disable")
        
        if count == 0:
            if verbosity >= 1:
                self.stdout.write(self.style.SUCCESS("No expired campaigns to disable"))
            return
        
        # Process each expired campaign
        for campaign in expired_campaigns:
            if verbosity >= 2:
                self.stdout.write(f"Campaign '{campaign.name}' expired on {campaign.end_date}")
            
            if not dry_run:
                campaign.active = False
                campaign.save()
                if verbosity >= 2:
                    self.stdout.write(self.style.SUCCESS(f"Disabled campaign: {campaign.name}"))
            else:
                if verbosity >= 2:
                    self.stdout.write(f"Would disable campaign: {campaign.name} [DRY RUN]")
        
        # Final summary
        if not dry_run:
            if verbosity >= 1:
                self.stdout.write(self.style.SUCCESS(f"Successfully disabled {count} expired campaign(s)"))
        else:
            if verbosity >= 1:
                self.stdout.write(f"Would disable {count} expired campaign(s) [DRY RUN]")
