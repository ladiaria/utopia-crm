# coding=utf-8
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core.models import DoNotCallNumber


class UploadDoNotCallNumbersTest(TestCase):
    """
    The view replaces the whole do not call list with an uploaded CSV. What matters here is that
    the previous list is really gone before the new one is inserted, that a bad file leaves the
    old list untouched, and that only admins can run it.
    """

    def setUp(self):
        self.url = reverse("upload_do_not_call_numbers")

        self.admin = User.objects.create_user(username="admin", password="secret", is_staff=True)
        admins_group, _created = Group.objects.get_or_create(name="Admins")
        self.admin.groups.add(admins_group)

        # Staff, but not in Admins: staff alone is no longer enough.
        self.staff = User.objects.create_user(username="staff", password="secret", is_staff=True)

        DoNotCallNumber.objects.bulk_create([DoNotCallNumber(number="0990000%02d" % i) for i in range(10)])

    def _login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def _upload(self, client, content, header_rows=2, follow=True):
        return client.post(
            self.url,
            {
                "do_not_call_numbers": SimpleUploadedFile("list.csv", content, content_type="text/csv"),
                "header_rows": header_rows,
            },
            follow=follow,
        )

    def test_staff_without_admins_group_is_rejected(self):
        response = self._upload(self._login(self.staff), b"h1\nh2\n099111222,\n", follow=False)
        # user_passes_test redirects to the login page instead of running the view.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DoNotCallNumber.objects.count(), 10)

    def test_anonymous_is_rejected(self):
        response = self._upload(Client(), b"h1\nh2\n099111222,\n", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DoNotCallNumber.objects.count(), 10)

    def test_replaces_the_whole_list(self):
        content = b"Numero de tramite: 2026-71-1\nFecha de consulta: 21/08/2026\n099111222,\n099333444,\n"
        response = self._upload(self._login(self.admin), content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(DoNotCallNumber.objects.values_list("number", flat=True)),
            {"099111222", "099333444"},
        )

    def test_repeated_numbers_do_not_break_the_upload(self):
        """A number repeated in the file used to abort the whole insert with an IntegrityError."""
        content = b"h1\nh2\n099111222,\n099111222,\n099333444,\n"
        self._upload(self._login(self.admin), content)
        self.assertEqual(DoNotCallNumber.objects.count(), 2)

    def test_a_number_already_stored_does_not_break_the_upload(self):
        """The old list must be gone before inserting, even when the new file repeats its numbers."""
        content = b"h1\nh2\n099000000,\n099111222,\n"
        self._upload(self._login(self.admin), content)
        self.assertEqual(
            set(DoNotCallNumber.objects.values_list("number", flat=True)),
            {"099000000", "099111222"},
        )

    def test_blank_and_oversized_rows_are_ignored(self):
        content = ("h1\nh2\n099111222,\n\n,\n%s,\n099333444,\n" % ("9" * 30)).encode("utf-8")
        self._upload(self._login(self.admin), content)
        self.assertEqual(
            set(DoNotCallNumber.objects.values_list("number", flat=True)),
            {"099111222", "099333444"},
        )

    def test_empty_file_keeps_the_previous_list(self):
        self._upload(self._login(self.admin), b"h1\nh2\n")
        self.assertEqual(DoNotCallNumber.objects.count(), 10)

    def test_latin1_file_is_accepted(self):
        content = "N\xfamero de tr\xe1mite\nFecha\n099111222,\n".encode("latin-1")
        self._upload(self._login(self.admin), content)
        self.assertEqual(set(DoNotCallNumber.objects.values_list("number", flat=True)), {"099111222"})

    def test_header_rows_is_honoured(self):
        content = b"099111222,\n099333444,\n"
        self._upload(self._login(self.admin), content, header_rows=0)
        self.assertEqual(DoNotCallNumber.objects.count(), 2)

    def test_missing_file_keeps_the_previous_list(self):
        c = self._login(self.admin)
        response = c.post(self.url, {"header_rows": 2}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DoNotCallNumber.objects.count(), 10)
