# coding=utf-8
from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from support.models import Issue, IssueStatus, IssueSubcategory, Seller
from support.views.seller_console import get_never_paid_subcategory_slugs

from .factory import create_contact


@override_settings(
    ISSUE_SUBCATEGORY_NEVER_PAID="never-paid-test", ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS=["never-paid-2-test"]
)
class SellerConsoleNeverPaidTest(TestCase):
    """
    The seller console lists the never paid issues of ISSUE_SUBCATEGORY_NEVER_PAID and of
    ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS assigned to the seller.

    The statuses and subcategories are built by hand: the base repo ships no issue catalogue fixture. Slugs are
    auto-generated from the name.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="vendedor", password="secret")
        cls.seller = Seller.objects.create(name="Vendedor", user=cls.user, internal=True)
        cls.status_new = IssueStatus.objects.create(name=settings.ISSUE_STATUS_NEW)
        cls.status_solved = IssueStatus.objects.create(name=settings.ISSUE_STATUS_SOLVED)
        cls.never_paid = IssueSubcategory.objects.create(name="never-paid-test", category="I")
        cls.never_paid_2 = IssueSubcategory.objects.create(name="never-paid-2-test", category="I")
        cls.debt = IssueSubcategory.objects.create(name="debt-test", category="I")

    def setUp(self):
        self.client.login(username="vendedor", password="secret")

    def _issue(self, sub_category, status=None, assigned_to=None):
        return Issue.objects.create(
            contact=create_contact("Contacto", "099111222", f"c{Issue.objects.count()}@example.com"),
            date=date.today(),
            category="I",
            sub_category=sub_category,
            status=status or self.status_new,
            assigned_to=assigned_to or self.user,
        )

    def test_slugs_include_the_extra_ones(self):
        self.assertEqual(get_never_paid_subcategory_slugs(), ["never-paid-test", "never-paid-2-test"])

    @override_settings(ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS=[])
    def test_slugs_without_extra(self):
        self.assertEqual(get_never_paid_subcategory_slugs(), ["never-paid-test"])

    @override_settings(ISSUE_SUBCATEGORY_NEVER_PAID=None)
    def test_no_slugs_without_never_paid(self):
        self.assertEqual(get_never_paid_subcategory_slugs(), [])

    def test_page_lists_both_subcategories(self):
        never_paid = self._issue(self.never_paid)
        never_paid_2 = self._issue(self.never_paid_2)
        self._issue(self.debt)
        self._issue(self.never_paid_2, status=self.status_solved)
        other_user = User.objects.create_user(username="otro", password="secret", is_staff=True)
        self._issue(self.never_paid_2, assigned_to=other_user)

        response = self.client.get(reverse("seller_console_never_paid_issues"))

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.context["issues_never_paid"], [never_paid, never_paid_2])
        self.assertTrue(response.context["show_subcategory"])

    @override_settings(ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS=[])
    def test_page_without_extra_hides_subcategory(self):
        never_paid = self._issue(self.never_paid)
        self._issue(self.never_paid_2)

        response = self.client.get(reverse("seller_console_never_paid_issues"))

        self.assertEqual(list(response.context["issues_never_paid"]), [never_paid])
        self.assertFalse(response.context["show_subcategory"])

    # Without routes: local_settings may list special routes that the test database doesn't have
    @override_settings(SPECIAL_ROUTES_FOR_SELLERS_LIST=[])
    def test_campaign_list_counts_both_subcategories(self):
        self._issue(self.never_paid)
        self._issue(self.never_paid_2)
        self._issue(self.debt)

        response = self.client.get(reverse("seller_console_list_campaigns"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["issues_never_paid_count"], 2)
