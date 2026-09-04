from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """
    Deprecated: replaced by close_lost_schedule_activities (t1175).

    This command used to close every pending or expired activity older than a date and force its
    ContactCampaignStatus to 'Ended without contact' with the 'CW' resolution, without checking
    whether the campaign status was already resolved. It was run in production on 2025-07-01 and
    overwrote 181 successful sales (S1/S2) along the way, and it sent contacts that had actually
    been spoken to into the 'ended without contact' bucket, distorting campaign statistics.

    It is kept as a stub, and not silently rewired to the new behaviour, so anyone who still has it
    in a runbook gets a clear message instead of a different semantics without noticing.
    """

    help = "Deprecated. Use close_lost_schedule_activities instead."

    def handle(self, *args, **options):
        raise CommandError(
            "This command is deprecated because it overwrote already resolved campaign statuses, sales "
            "included. Use 'close_lost_schedule_activities' instead:\n"
            "    python manage.py close_lost_schedule_activities --date YYYY-MM-DD --dry-run"
        )
