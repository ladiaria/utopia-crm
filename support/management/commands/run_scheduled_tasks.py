# coding=utf-8
from datetime import date, timedelta

from django.core.management import BaseCommand
from support.models import ScheduledTask


class Command(BaseCommand):
    help = u"Executes pending scheduled tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbosity',
            default=1,
            type=int,
            choices=[0, 1, 2, 3],
            help='Verbosity level; 0=minimal output, 1=normal output, 2=verbose output, 3=very verbose output',
        )

    def handle(self, *args, **options):
        verbosity = options['verbosity']
        tasks = ScheduledTask.objects.filter(execution_date__lte=date.today() + timedelta(1), completed=False)

        if verbosity >= 2:
            self.stdout.write(f"Found {tasks.count()} tasks to execute")

        for task in tasks:
            response = task.execute(verbose=verbosity >= 2)
            if response and verbosity >= 1:
                self.stdout.write(response)
