import io
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from reportlab.pdfgen.canvas import Canvas

from logistics.labels import LogisticsLabel, LogisticsLabel96x30, Roll, Roll96x30, SheetA4, LogisticsLabelA4


class FlushTestCase(SimpleTestCase):
    def test_without_labels_the_pdf_is_valid(self):
        for sheet_type, label_type in (
            (Roll, LogisticsLabel),
            (Roll96x30, LogisticsLabel96x30),
            (SheetA4, LogisticsLabelA4),
        ):
            with self.subTest(sheet_type.__name__):
                pdf = io.BytesIO()
                canvas = Canvas(pdf, pagesize=(sheet_type.width, sheet_type.height))
                sheet = sheet_type(label_type, canvas)
                sheet.iterator()  # As the views do: the generator doesn't start until the first label

                sheet.flush()
                canvas.save()

                self.assertTrue(pdf.getvalue().startswith(b"%PDF"))
                self.assertEqual(canvas.getPageNumber(), 2)

    def test_without_labels_the_page_says_so(self):
        canvas = MagicMock()

        Roll(LogisticsLabel, canvas).flush()

        self.assertIn("labels to print", canvas.drawString.call_args.args[2].lower())
        canvas.restoreState.assert_not_called()

    def test_with_a_label_it_restores_the_state_and_writes_nothing(self):
        pdf = io.BytesIO()
        canvas = Canvas(pdf, pagesize=(Roll.width, Roll.height))
        sheet = Roll(LogisticsLabel, canvas)
        label = next(sheet.iterator())
        label.name = "Ana"
        label.draw()

        sheet.flush()
        canvas.save()

        self.assertTrue(sheet.has_labels)
        self.assertTrue(pdf.getvalue().startswith(b"%PDF"))


class ScreensWithoutLabelsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="staff", is_staff=True, is_superuser=True)

    def setUp(self):
        self.client.force_login(self.user)

    def assertPdf(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_print_labels_for_day(self):
        self.assertPdf(self.client.post(reverse("print_labels_for_day"), {"isoweekday": "1"}))

    def test_print_labels_for_day_96x30(self):
        self.assertPdf(self.client.post(reverse("print_labels_for_day"), {"isoweekday": "1", "96x30": "1"}))

    def test_print_labels_from_csv_with_only_the_header(self):
        file = SimpleUploadedFile("etiquetas.csv", b"name,address,city,route,order,message,suffix\n")

        self.assertPdf(self.client.post(reverse("print_labels_from_csv"), {"labels": file}))

    def test_print_labels(self):
        url = reverse("print_labels", kwargs={"page": "Roll"})

        self.assertPdf(self.client.post(url, {"product_id": ""}))
