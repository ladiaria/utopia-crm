from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from core.models import Activity, ContactCampaignStatus
from core.choices import ACTIVITY_STATUS
from support.models import SellerConsoleAction


class Command(BaseCommand):
    help = (
        "Closes pending and expired activities older than a specified date and their related campaign statuses. "
        "The activities will be marked as completed and assigned the 'close-without-contact' action. "
        "If there's a related ContactCampaignStatus, it will be marked as 'Ended without contact' "
        "with a campaign resolution of 'CW'. This command handles both pending activities that need to be closed "
        "and expired activities that were previously marked as expired but still need campaign status updates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            required=True,
            help="Date in YYYY-MM-DD format. Activities with this date or older will be closed.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run in dry-run mode (don't actually update records).",
        )

    def handle(self, *args, **options):
        date_str = options["date"]
        dry_run = options["dry_run"]

        try:
            # Parse the date string and set it to the beginning of the day
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            target_date = timezone.make_aware(target_date)

            # Get the seller console action
            try:
                seller_action = SellerConsoleAction.objects.get(slug="close-without-contact")
            except SellerConsoleAction.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        "SellerConsoleAction with slug 'close-without-contact' does not exist. "
                        "Please run 'python manage.py populate_seller_console_actions' first."
                    )
                )
                return

            # Find all pending and expired activities older than or equal to the target date
            activities = Activity.objects.filter(
                status__in=[ACTIVITY_STATUS.PENDING, ACTIVITY_STATUS.EXPIRED],
                datetime__lte=target_date
            )

            total_activities = activities.count()
            
            # Get breakdown by status
            pending_count = activities.filter(status=ACTIVITY_STATUS.PENDING).count()
            expired_count = activities.filter(status=ACTIVITY_STATUS.EXPIRED).count()
            
            self.stdout.write(f"Found {total_activities} activities to close:")
            self.stdout.write(f"  - Pending activities: {pending_count}")
            self.stdout.write(f"  - Expired activities: {expired_count}")

            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made."))
                return

            # Counter for related campaign statuses
            campaign_statuses_updated = 0

            # Process each activity
            with transaction.atomic():
                for activity in activities:
                    # Update the activity
                    activity.status = ACTIVITY_STATUS.COMPLETED  # Completed
                    activity.seller_console_action = seller_action
                    activity.save()

                    # Check if there's a related ContactCampaignStatus
                    if activity.contact and activity.campaign:
                        try:
                            campaign_status = ContactCampaignStatus.objects.get(
                                contact=activity.contact,
                                campaign=activity.campaign
                            )
                            # Update the campaign status
                            campaign_status.status = 5  # Ended without contact
                            campaign_status.campaign_resolution = "CW"  # Close without contact
                            campaign_status.save()
                            campaign_statuses_updated += 1
                        except ContactCampaignStatus.DoesNotExist:
                            # No related campaign status found, continue
                            pass

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully closed {total_activities} activities and updated "
                    f"{campaign_statuses_updated} related campaign statuses."
                )
            )

        except ValueError:
            self.stderr.write(
                self.style.ERROR("Invalid date format. Please use YYYY-MM-DD format.")
            )
