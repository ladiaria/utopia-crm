# coding=utf-8
from datetime import date, timedelta

from django.utils.translation import ugettext_lazy as _
from django.core.management import BaseCommand

from core.models import ContactProductHistory, SubscriptionProduct
from support.models import ScheduledTask
from logistics.models import RouteChange


class Command(BaseCommand):
    help = u"Executes pending scheduled tasks"
    """
    These are the categories for the scheduled tasks:
        'AC': 'Address change'
        'PD': 'De-activation (Pause)'
        'PA': 'Activation (Pause)'
    """

    # This is left blank if it's necessary to add some arguments
    # def add_arguments(self, parser):
    #    # parser.add_argument('payment_type', type=str)

    def handle(self, *args, **options):
        # We'll get all the Scheduled Tasks that are supposed to be executed until tomorrow
        tasks = ScheduledTask.objects.filter(execution_date__lte=date.today() + timedelta(1), completed=False)
        for task in tasks:
            # For each task we'll check what we need to do with it
            if task.category == 'PD':  # Start of pause
                contact = task.contact
                subscription = task.subscription
                print(
                    _(
                        "Executing start of pause scheduled task for {}'s subscription {}".format(
                            contact.id, subscription.id
                        )
                    )
                )
                subscription.active, subscription.status = False, 'PA'
                # Then we need to check if we need to change the next billing, if this task is ending another one.
                if task.ends:
                    deactivation_task = task.ends
                    # We need to calculate the difference in days, this is gonna result in a timedelta object
                    date_difference = task.execution_date - deactivation_task.execution_date
                    # Next we need to sum that timedelta object
                    subscription.next_billing = subscription.next_billing + date_difference
                subscription.save()
                # Then we'll set the task as completed
                task.completed = True
                task.save()
                print(_("Task {} completed successfully.".format(task.id)))

            elif task.category == 'PA':  # End of pause
                contact = task.contact
                subscription = task.subscription
                print(
                    _(
                        "Executing end of pause scheduled task for {} subscription {}".format(
                            contact.id, subscription.id
                        )
                    )
                )
                subscription.active = True
                # We're going to create new contact product histories as this contact is now active again
                for sp in SubscriptionProduct.objects.filter(subscription=subscription):
                    ContactProductHistory.objects.create(
                        contact=contact,
                        subscription=subscription,
                        product=sp.product,
                        status='A',
                        date=date.today(),
                    )
                # The status of the subscription is going to be OK again
                subscription.status = 'OK'
                # We don't need to change any next_billing since that has been done in the previous run
                subscription.save()
                task.completed = True
                task.save()
                print(_("Task {} completed successfully.".format(task.id)))

            elif task.category == 'AC':
                contact = task.contact
                subscription = task.subscription
                address = task.address
                print(_("Executing address change scheduled task for contact {}".format(contact.id)))
                for sp in task.subscription_products.all():
                    # We need to change the address for said subscription_product
                    if sp.route:
                        rc = RouteChange.objects.create(
                            product=sp.product,
                            old_route=sp.route,
                            contact=task.contact,
                        )
                        if sp.address:
                            rc.old_address = u"{} {}".format(sp.address.address_1, sp.address.address_2 or '')
                            rc.old_city = sp.address.city or ''
                            rc.save()
                    sp.address = address
                    # After this, we will delete their route anr orders
                    sp.route = None
                    sp.order = None
                    sp.label_message = task.label_message
                    sp.special_instructions = task.speciak_instructions
                    sp.save()
                task.completed = True
                task.save()
                print(_("Task {} completed successfully.".format(task.id)))
