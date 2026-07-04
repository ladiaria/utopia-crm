from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from core.models import Activity
from core.choices import ACTIVITY_STATUS


class Command(BaseCommand):
    help = (
        "Expires pending activities that are older than the current datetime. "
        "This command should be run at midnight or as a scheduled task to "
        "automatically mark old pending activities as expired."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be expired without making changes',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=0,
            help='Only expire activities older than N days from now (default: 0, expires all past activities)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days_threshold = options['days']
        
        # Calculate the cutoff datetime
        now = timezone.now()
        if days_threshold > 0:
            from datetime import timedelta
            cutoff_datetime = now - timedelta(days=days_threshold)
            self.stdout.write(
                f"Looking for pending activities older than {cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            cutoff_datetime = now
            self.stdout.write(
                f"Looking for pending activities older than {cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # Find pending activities that are past their datetime
        pending_activities = Activity.objects.filter(
            status=ACTIVITY_STATUS.PENDING,
            datetime__lt=cutoff_datetime
        ).select_related('contact', 'campaign')

        activities_count = pending_activities.count()
        
        if activities_count == 0:
            self.stdout.write(
                self.style.SUCCESS("No pending activities found to expire.")
            )
            return

        self.stdout.write(
            f"Found {activities_count} pending activities to expire."
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - No changes will be made.")
            )
            for activity in pending_activities[:10]:  # Show first 10 as examples
                self.stdout.write(
                    f"  - Activity {activity.id} for contact {activity.contact_id} "
                    f"(scheduled: {activity.datetime.strftime('%Y-%m-%d %H:%M:%S')})"
                )
            if activities_count > 10:
                self.stdout.write(f"  ... and {activities_count - 10} more activities")
            return

        # Update activities to expired status
        expired_count = 0
        
        with transaction.atomic():
            for activity in pending_activities:
                activity.status = ACTIVITY_STATUS.EXPIRED
                activity.save()
                expired_count += 1
                
                if expired_count % 100 == 0:
                    self.stdout.write(f"Expired {expired_count} activities...")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully expired {expired_count} activities."
            )
        )

        # Summary
        self.stdout.write(
            f"\nSummary:"
            f"\n  - Total activities expired: {expired_count}"
            f"\n  - Cutoff datetime: {cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
        )