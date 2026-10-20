from datetime import date, timedelta

from django.core.management import BaseCommand
from support.models import ScheduledTask, ScheduledTaskMissingAddress

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - sentry_sdk debería estar instalado en producción
    sentry_sdk = None


class Command(BaseCommand):
    help = u"Executes pending scheduled tasks"

    def handle(self, *args, **options):
        verbosity = options.get('verbosity', 1)
        tasks = ScheduledTask.objects.filter(execution_date__lte=date.today() + timedelta(1), completed=False)

        if verbosity >= 2:
            self.stdout.write(f"Found {tasks.count()} tasks to execute")

        for task in tasks:
            try:
                response = task.execute(verbose=verbosity >= 2)
            except ScheduledTaskMissingAddress as exc:
                # Not a crash: someone deleted the address. It stays pending, so it comes back every day: one Sentry
                # issue per task (fingerprint) instead of a new one each run. The mail went out when it was deleted.
                product_ids = list(task.subscription_products.values_list("id", flat=True))
                self.stderr.write(f"{exc} (contact_id={task.contact_id}, subscription_product_ids={product_ids})")
                if sentry_sdk is not None:
                    with sentry_sdk.push_scope() as scope:
                        scope.fingerprint = ["scheduled-task-missing-address", str(task.id)]
                        scope.set_context(
                            "scheduled_task",
                            {
                                "id": task.id,
                                "category": task.category,
                                "contact_id": task.contact_id,
                                "subscription_product_ids": product_ids,
                                "execution_date": str(task.execution_date),
                            },
                        )
                        sentry_sdk.capture_message(str(exc), level="warning")
                continue
            except Exception as exc:
                self.stderr.write(
                    f"Error executing ScheduledTask {task.id} "
                    f"(category={task.category}, contact_id={task.contact_id}): {exc!r}"
                )
                if sentry_sdk is not None:
                    with sentry_sdk.push_scope() as scope:
                        scope.set_context(
                            "scheduled_task",
                            {
                                "id": task.id,
                                "category": task.category,
                                "contact_id": task.contact_id,
                                "subscription_id": task.subscription_id,
                                "execution_date": str(task.execution_date),
                            },
                        )
                        sentry_sdk.capture_exception(exc)
                continue
            if response and verbosity >= 1:
                self.stdout.write(response)
