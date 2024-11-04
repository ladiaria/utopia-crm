from datetime import date, timedelta

from django.core.management import BaseCommand
from support.models import ScheduledTask


class Command(BaseCommand):
    help = u"Executes pending scheduled tasks"

    def handle(self, *args, **options):
        verbosity = options.get('verbosity', 1)
        tasks = ScheduledTask.objects.filter(execution_date__lte=date.today() + timedelta(1), completed=False)

        if verbosity >= 2:
            self.stdout.write(f"Found {tasks.count()} tasks to execute")

        for task in tasks:
            response = task.execute(verbose=verbosity >= 2)
            if response and verbosity >= 1:
                self.stdout.write(response)
