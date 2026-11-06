from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import Contact, ContactCampaignStatus, DoNotCallNumber
from tests.factories import CampaignFactory, ContactFactory


def uploaded(content, encoding="utf-8"):
    return SimpleUploadedFile("planilla.csv", content.encode(encoding), content_type="text/csv")


class CsvUploadTestCase(TestCase):
    """What a spreadsheet saves: a BOM with "CSV UTF-8", cp1252 with plain "CSV", semicolons with a Spanish locale."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="staff", is_staff=True, is_superuser=True)
        cls.user.groups.add(Group.objects.get_or_create(name="Admins")[0])
        cls.ana = ContactFactory(name="Ana", last_name="Pérez", email="ana@example.com")
        cls.beto = ContactFactory(name="Beto", last_name="Rey", email="beto@example.com")

    def setUp(self):
        self.client.force_login(self.user)


class TagContactsTestCase(CsvUploadTestCase):
    def upload(self, file):
        return self.client.post(reverse("tag_contacts"), {"file": file}, follow=True)

    def contact_tags(self, contact):
        return sorted(tag.name for tag in Contact.objects.get(pk=contact.pk).tags.all())

    def test_bom_does_not_skip_the_first_row(self):
        self.upload(uploaded(f"{self.ana.id},campana\n{self.beto.id},campana\n", "utf-8-sig"))

        self.assertEqual(self.contact_tags(self.ana), ["campana"])
        self.assertEqual(self.contact_tags(self.beto), ["campana"])

    def test_semicolons(self):
        self.upload(uploaded(f"{self.ana.id};campana\n{self.beto.id};campana\n"))

        self.assertEqual(self.contact_tags(self.ana), ["campana"])

    def test_row_without_tag_does_not_fail_and_the_rest_is_tagged(self):
        response = self.upload(uploaded(f"{self.ana.id}\n{self.beto.id},campana\n"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.contact_tags(self.ana), [])
        self.assertEqual(self.contact_tags(self.beto), ["campana"])
        self.assertTrue(any("1" in str(m) and "tag" in str(m).lower() for m in get_messages(response.wsgi_request)))


class DoNotCallTestCase(CsvUploadTestCase):
    def upload(self, content, encoding="utf-8", header_rows=0):
        data = {"do_not_call_numbers": uploaded(content, encoding), "header_rows": header_rows}
        return self.client.post(reverse("upload_do_not_call_numbers"), data, follow=True)

    def numbers(self):
        return sorted(DoNotCallNumber.objects.values_list("number", flat=True))

    def test_bom_does_not_end_up_in_the_first_number(self):
        self.upload("099123456\n099654321\n", "utf-8-sig")

        self.assertEqual(self.numbers(), ["099123456", "099654321"])

    def test_semicolons_keep_only_the_number(self):
        self.upload("099123456;Ana\n099654321;Beto\n")

        self.assertEqual(self.numbers(), ["099123456", "099654321"])


class BulkDeleteCampaignStatusTestCase(CsvUploadTestCase):
    def upload(self, file):
        campaign = CampaignFactory()
        status = ContactCampaignStatus.objects.create(contact=self.ana, campaign=campaign)
        url = reverse("bulk_delete_campaign_status")
        response = self.client.post(url, {"csv_file": file, "campaign": campaign.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        return ContactCampaignStatus.objects.filter(pk=status.pk).exists()

    def test_plain_excel_csv(self):
        self.assertFalse(self.upload(uploaded(f"contact_id,nombre\n{self.ana.id},José\n", "cp1252")))

    def test_bom(self):
        self.assertFalse(self.upload(uploaded(f"contact_id\n{self.ana.id}\n", "utf-8-sig")))

    def test_row_with_more_columns_than_the_header(self):
        self.assertFalse(self.upload(uploaded(f"contact_id\n{self.ana.id},sobra\n")))


class ImportContactsTestCase(CsvUploadTestCase):
    def upload(self, file):
        return self.client.post(
            reverse("import_contacts"), {"file": file, "use_headers": "on", "tags": "planilla"}, follow=True
        )

    def row(self, delimiter=",", extra=()):
        columns = [
            "name", "last_name", "email", "phone", "mobile", "notes", "address_1", "address_2", "city", "state",
            "country", "id_document_type", "id_document",
        ]  # fmt: skip
        values = ["Carla", "Díaz", "carla@gmail.com"] + [""] * (len(columns) - 3) + list(extra)
        return f"{delimiter.join(columns)}\n{delimiter.join(values)}\n"

    def assertImported(self):
        self.assertTrue(Contact.objects.filter(email="carla@gmail.com", name="Carla", last_name="Díaz").exists())

    def test_semicolons(self):
        self.upload(uploaded(self.row(";")))

        self.assertImported()

    def test_bom(self):
        self.upload(uploaded(self.row(), "utf-8-sig"))

        self.assertImported()

    def test_plain_excel_csv(self):
        self.upload(uploaded(self.row(), "cp1252"))

        self.assertImported()

    def test_row_with_more_columns_than_the_header_does_not_shift_the_data(self):
        # pandas would otherwise take the first column as an index: the name would go to the last name
        self.upload(uploaded(self.row(extra=["sobra"])))

        self.assertImported()


class PrintLabelsTestCase(CsvUploadTestCase):
    def assertPdf(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_labels_from_semicolon_csv(self):
        content = "name;address;city;route;order;message;suffix\nAna;Calle 1, apto 2;Montevideo;1;2;;\n"
        file = uploaded(content, "utf-8-sig")

        self.assertPdf(self.client.post(reverse("print_labels_from_csv"), {"labels": file}))

    def test_labels_from_plain_excel_csv(self):
        content = "name,address,city,route,order,message,suffix\nJosé,Calle 1,Montevideo,1,2,,\n"
        file = uploaded(content, "cp1252")

        self.assertPdf(self.client.post(reverse("print_labels_from_csv"), {"labels": file}))

    # Without labels to draw the PDF itself fails, and these two are about reading the file
    @patch("logistics.views.Canvas")
    def test_print_labels_for_day_excludes_contacts(self, _canvas):
        file = uploaded(f"contact_id\n{self.ana.id}\n", "utf-8-sig")

        response = self.client.post(reverse("print_labels_for_day"), {"exclude_contacts": file, "isoweekday": "1"})

        self.assertPdf(response)

    @patch("logistics.views.Canvas")
    def test_print_labels_marks_contacts_with_a_header_and_a_bom(self, _canvas):
        file = uploaded(f"contact_id\n{self.ana.id}\n", "utf-8-sig")
        url = reverse("print_labels", kwargs={"page": "Roll"})

        self.assertPdf(self.client.post(url, {"mark_contacts": file, "product_id": ""}))
