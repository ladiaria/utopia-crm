from django.test import TestCase, Client, override_settings
from django.urls import reverse
from tests.factory import create_contact

from support.models import IssueSubcategory, IssueStatus, Issue


class CreateIssueApiTests(TestCase):
    """
    Test the create_issue_api view via the API.
    """

    def setUp(self):
        # We're going to create a subcategory for the issue. The category is "S" for "Service".
        # A slug will be automatically created from the name.
        IssueSubcategory.objects.create(name="Welcome call", category="S")
        # Same for the status. The slug will be automatically created from the name.
        IssueStatus.objects.create(name="New")

    # We then override the settings to set the API key and the status for the issue.
    # Those should already be set in the settings file, but we want to make sure we're testing with the right values.
    @override_settings(CRM_API_KEY="1234", ISSUE_STATUS_NEW='new')
    def test_create_issue_api(self):
        c = Client()
        contact_obj = create_contact("Fake Contact", "29000808")
        url = reverse("create_issue_api")
        data = {
            "api_key": "1234",
            "contact_id": contact_obj.id,
            "sub_category": "welcome-call",
            "notes": "test",
        }
        response = c.post(url, data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"issue_id": 1})

        issue_obj = Issue.objects.get(pk=1)
        self.assertTrue(isinstance(issue_obj, Issue))
        self.assertEqual(issue_obj.contact, contact_obj)
        self.assertEqual(issue_obj.sub_category.slug, "welcome-call")
        self.assertEqual(issue_obj.notes, "test")
