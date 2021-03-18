# coding=utf-8
from datetime import date

from django.utils.translation import ugettext_lazy as _
from django.core.management import BaseCommand
from django.conf import settings

from core.models import ContactProductHistory, SubscriptionProduct
from support.models import ScheduledTask, IssueStatus
from logistics.models import RouteChange


class Command(BaseCommand):
    help = """Executes scheduled tasks daily"""
    """
    These are the categories for the scheduled tasks:
    ('AC', 'Address change'),
    ('PD', 'De-activation (Pause)'),
    ('PA', 'Activation (Pause)'),
    """

    # This is left blank if it's necessary to add some arguments
    # def add_arguments(self, parser):
    #    # parser.add_argument('payment_type', type=str)

    def handle(self, *args, **options):
        # We'll get all the Scheduled Tasks that are supposed to be executed today
        tasks = ScheduledTask.objects.filter(execution_date__lte=date.today(), completed=False)
        for task in tasks:
            # For each task we'll check what we need to do with it
            if task.category == 'PD':
                contact = task.contact
                subscription = task.subscription
                print(_("Started deactivation (start of pause) scheduled task for {}'s subscription {}".format(
                    contact, subscription)))
                subscription.active = False
                # We're going to create contact product histories showing that this contact is now paused for all
                # these products
                for sp in SubscriptionProduct.objects.filter(subscription=subscription):
                    ContactProductHistory.objects.create(
                        contact=contact,
                        subscription=subscription,
                        product=sp.product,
                        status='P')
                subscription.status = 'PA'
                # Then we need to check if we need to change the next billing, if there is an activation event
                # associated with the same issue.
                if ScheduledTask.objects.filter(issue=task.issue).count() == 2:
                    activation_task = ScheduledTask.objects.get(issue=task.issue, category='PA')
                    # We need to calculate the difference in days, this is gonna result in a timedelta object
                    date_difference = activation_task.execution_date - task.execution_date
                    # Next we need to sum that timedelta object
                    subscription.next_billing = subscription.next_billing + date_difference
                subscription.save()
                # Then we'll set the task as completed
                task.completed = True
                task.save()
                issue = task.issue
                issue.status = IssueStatus.objects.get(slug=settings.SOLVED_ISSUE_STATUS_SLUG)
                issue.closing_date = date.today()
                issue.save()
                print(_("Task {} completed successfully.".format(task.id)))

            elif task.category == 'PA':
                contact = task.contact
                subscription = task.subscription
                print(_("Started activation (end of pause) scheduled task for {}'s subscription {}".format(
                    contact, subscription)))
                subscription.active = True
                # We're going to create new contact product histories as this contact is now active again
                for sp in SubscriptionProduct.objects.filter(subscription=subscription):
                    ContactProductHistory.objects.create(
                        contact=contact,
                        subscription=subscription,
                        product=sp.product,
                        status='A')
                # The status of the subscription is going to be OK again
                subscription.status = 'OK'
                # We don't need to change any next_billing since that has been done in the previous run
                subscription.save()
                task.completed = True
                task.save()
                issue.status = IssueStatus.objects.get(slug=settings.SOLVED_ISSUE_STATUS_SLUG)
                issue.closing_date = date.today()
                issue.save()
                print(_("Task {} completed successfully.".format(task.id)))

            elif task.category == 'AC':
                contact = task.contact
                subscription = task.subscription
                address = task.address
                print(_("Started address change scheduled task for {}'".format(contact)))
                for sp in task.subscription_products.all():
                    # We need to change the address for said subscription_product
                    rc = RouteChange.objects.create(
                        product=sp.product,
                        old_route=sp.route,
                        contact=task.contact,
                    )
                    if sp.address:
                        rc.old_address = "{} {}".format(sp.address.address_1, sp.address.address_2 or '')
                        rc.old_city = sp.address.city or ''
                        rc.save()
                    sp.address = address
                    # After this, we will delete their route anr orders
                    sp.route = None
                    sp.order = None
                    sp.save()
                task.completed = True
                task.save()
                issue.status = IssueStatus.objects.get(slug=settings.SOLVED_ISSUE_STATUS_SLUG)
                issue.closing_date = date.today()
                issue.save()
                print(_("Task {} completed successfully.".format(task.id)))
