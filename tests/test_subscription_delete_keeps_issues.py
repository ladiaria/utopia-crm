# coding=utf-8
"""
Deleting a subscription keeps its issues and their activities (SET_NULL, it/utopia-crm-ladiaria#192).

They are the contact's history. Before this they went away with the subscription, and the admin asked for the delete
permission on issues and activities to delete a subscription. Its scheduled tasks and sales records still go with it:
without the subscription they mean nothing.
"""
from datetime import date

from django.test import TestCase, override_settings

from core.models import Activity
from support.models import Issue, SalesRecord, ScheduledTask

from tests.factory import create_contact, create_subscription


@override_settings(WEB_UPDATE_USER_ENABLED=False)
class TestSubscriptionDeleteKeepsIssues(TestCase):
    def setUp(self):
        self.contact = create_contact(name="Historia", phone="099444222")
        self.subscription = create_subscription(self.contact)

    def test_deleting_a_subscription_keeps_its_issues_and_activities(self):
        issue = Issue.objects.create(contact=self.contact, date=date.today(), subscription=self.subscription)
        activity = Activity.objects.create(contact=self.contact, issue=issue)
        self.subscription.delete()
        self.assertIsNone(Issue.objects.get(pk=issue.pk).subscription)
        self.assertEqual(Activity.objects.get(pk=activity.pk).issue_id, issue.pk)

    def test_deleting_a_subscription_deletes_its_scheduled_tasks_and_sales_records(self):
        task = ScheduledTask.objects.create(
            contact=self.contact, category="PA", execution_date=date.today(), subscription=self.subscription
        )
        record = SalesRecord.objects.create(subscription=self.subscription)
        self.subscription.delete()
        self.assertFalse(ScheduledTask.objects.filter(pk=task.pk).exists())
        self.assertFalse(SalesRecord.objects.filter(pk=record.pk).exists())
