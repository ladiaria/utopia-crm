# coding=utf-8
from datetime import time

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from support.models import (
    AbsenceReason,
    AttendanceRecord,
    Seller,
    SellerAttendance,
    Shift,
    ATTENDANCE_STATUS_ABSENT,
    ATTENDANCE_STATUS_PRESENT,
)


def create_shift(name="Matutino", start=time(9, 0), end=time(17, 0)):
    return Shift.objects.create(name=name, start_time=start, end_time=end)


def create_absence_reason(name="Enfermedad", justified=True, active=True):
    return AbsenceReason.objects.create(name=name, justified=justified, active=active)


def create_seller(name="Test Seller", call_center=True, shift=None):
    return Seller.objects.create(name=name, call_center=call_center, shift=shift)


class AbsenceReasonStrTest(TestCase):
    def test_str_justified(self):
        from django.utils.translation import override
        reason = AbsenceReason(name="Médico", justified=True)
        with override("en"):
            self.assertIn("Justified", str(reason))

    def test_str_unjustified(self):
        from django.utils.translation import override
        reason = AbsenceReason(name="Personal", justified=False)
        with override("en"):
            self.assertIn("Unjustified", str(reason))


class AttendanceRecordUniquenessTest(TestCase):
    def test_duplicate_date_raises(self):
        from datetime import date
        d = date(2026, 1, 15)
        AttendanceRecord.objects.create(date=d)
        with self.assertRaises(IntegrityError):
            AttendanceRecord.objects.create(date=d)


class AbsenceReasonProtectTest(TestCase):
    def test_cannot_delete_reason_in_use(self):
        from datetime import date
        shift = create_shift()
        seller = create_seller(shift=shift)
        reason = create_absence_reason()
        record = AttendanceRecord.objects.create(date=date(2026, 1, 20))
        SellerAttendance.objects.create(
            record=record,
            seller=seller,
            status=ATTENDANCE_STATUS_ABSENT,
            absence_reason=reason,
            shift_start=time(9, 0),
            shift_end=time(17, 0),
        )
        with self.assertRaises(ProtectedError):
            reason.delete()


class SellerAttendanceViewGetTest(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user("staff", password="pass", is_staff=True)
        self.client.login(username="staff", password="pass")
        self.shift = create_shift()

    def test_get_no_prior_data(self):
        create_seller(name="Vendedor A", shift=self.shift)
        response = self.client.get(reverse("seller_attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vendedor A")

    def test_get_with_prior_data(self):
        from datetime import date
        seller = create_seller(name="Vendedor B", shift=self.shift)
        reason = create_absence_reason()
        record = AttendanceRecord.objects.create(date=date(2026, 2, 1))
        SellerAttendance.objects.create(
            record=record,
            seller=seller,
            status=ATTENDANCE_STATUS_ABSENT,
            absence_reason=reason,
            shift_start=time(9, 0),
            shift_end=time(17, 0),
        )
        response = self.client.get(reverse("seller_attendance") + "?date=2026-02-01")
        self.assertEqual(response.status_code, 200)
        seller_rows = response.context["seller_rows"]
        row = next(r for r in seller_rows if r["seller"].pk == seller.pk)
        self.assertEqual(row["status"], ATTENDANCE_STATUS_ABSENT)

    def test_only_call_center_sellers_shown(self):
        create_seller(name="CC Seller", call_center=True, shift=self.shift)
        create_seller(name="Non-CC Seller", call_center=False)
        response = self.client.get(reverse("seller_attendance"))
        names = [r["seller"].name for r in response.context["seller_rows"]]
        self.assertIn("CC Seller", names)
        self.assertNotIn("Non-CC Seller", names)


class SellerAttendanceViewPostTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser("admin", password="pass")
        self.client.login(username="admin", password="pass")
        self.shift = create_shift()
        self.seller = create_seller(name="Vendedor C", shift=self.shift)
        self.reason = create_absence_reason()

    def _post(self, date_str, extra_data=None):
        data = {"date": date_str}
        if extra_data:
            data.update(extra_data)
        return self.client.post(reverse("seller_attendance"), data)

    def test_post_present(self):
        data = {
            f"status-{self.seller.pk}": ATTENDANCE_STATUS_PRESENT,
            f"shift_start-{self.seller.pk}": "09:00",
            f"shift_end-{self.seller.pk}": "17:00",
        }
        response = self._post("2026-03-01", data)
        self.assertEqual(response.status_code, 302)
        att = SellerAttendance.objects.get(seller=self.seller)
        self.assertEqual(att.status, ATTENDANCE_STATUS_PRESENT)
        self.assertIsNone(att.absence_reason)

    def test_post_absent_with_reason(self):
        data = {
            f"status-{self.seller.pk}": ATTENDANCE_STATUS_ABSENT,
            f"reason-{self.seller.pk}": str(self.reason.pk),
            f"shift_start-{self.seller.pk}": "09:00",
            f"shift_end-{self.seller.pk}": "17:00",
        }
        response = self._post("2026-03-02", data)
        self.assertEqual(response.status_code, 302)
        att = SellerAttendance.objects.get(seller=self.seller)
        self.assertEqual(att.status, ATTENDANCE_STATUS_ABSENT)
        self.assertEqual(att.absence_reason, self.reason)

    def test_post_absent_without_reason_fails(self):
        data = {
            f"status-{self.seller.pk}": ATTENDANCE_STATUS_ABSENT,
            f"shift_start-{self.seller.pk}": "09:00",
            f"shift_end-{self.seller.pk}": "17:00",
        }
        response = self._post("2026-03-03", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SellerAttendance.objects.filter(seller=self.seller).exists())

    def test_post_without_shift_times_fails(self):
        data = {
            f"status-{self.seller.pk}": ATTENDANCE_STATUS_PRESENT,
        }
        response = self._post("2026-03-04", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SellerAttendance.objects.filter(seller=self.seller).exists())

    def test_post_by_non_superuser_forbidden(self):
        staff_only = User.objects.create_user("staffonly", password="pass", is_staff=True)
        self.client.login(username="staffonly", password="pass")
        data = {
            f"status-{self.seller.pk}": ATTENDANCE_STATUS_PRESENT,
            f"shift_start-{self.seller.pk}": "09:00",
            f"shift_end-{self.seller.pk}": "17:00",
        }
        response = self._post("2026-03-05", data)
        self.assertEqual(response.status_code, 403)

    def test_post_without_active_reasons_fails(self):
        self.reason.active = False
        self.reason.save()
        data = {
            f"status-{self.seller.pk}": ATTENDANCE_STATUS_ABSENT,
            f"shift_start-{self.seller.pk}": "09:00",
            f"shift_end-{self.seller.pk}": "17:00",
        }
        response = self._post("2026-03-06", data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SellerAttendance.objects.filter(seller=self.seller).exists())

    def test_post_upserts_existing(self):
        from datetime import date
        record = AttendanceRecord.objects.create(date=date(2026, 3, 10))
        SellerAttendance.objects.create(
            record=record,
            seller=self.seller,
            status=ATTENDANCE_STATUS_PRESENT,
            shift_start=time(9, 0),
            shift_end=time(17, 0),
        )
        data = {
            f"status-{self.seller.pk}": ATTENDANCE_STATUS_ABSENT,
            f"reason-{self.seller.pk}": str(self.reason.pk),
            f"shift_start-{self.seller.pk}": "09:00",
            f"shift_end-{self.seller.pk}": "17:00",
        }
        self._post("2026-03-10", data)
        self.assertEqual(SellerAttendance.objects.filter(seller=self.seller, record=record).count(), 1)
        att = SellerAttendance.objects.get(seller=self.seller, record=record)
        self.assertEqual(att.status, ATTENDANCE_STATUS_ABSENT)
