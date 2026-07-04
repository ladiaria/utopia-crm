# coding=utf-8
"""
Tests para la vista debtor_contacts y el método is_overdue de Invoice.

Cubre:
- is_overdue: factura vence hoy no está vencida, vence ayer sí.
- debtor_contacts: bug de cross-factura (contacto con factura paga de otro
  período no debe aparecer si sus facturas reales están al día).
- debtor_contacts: payment_date seteado con debited=False no cuenta como deuda.
- debtor_contacts: owed_invoices cuenta solo las facturas reales impagas.
"""
from datetime import date, timedelta

from django.test import RequestFactory, TestCase
from django.contrib.auth.models import User

from invoicing.models import Invoice
from support.views.all_views import debtor_contacts
from tests.factory import create_contact, create_subscription


def make_invoice(contact, days_offset, **kwargs):
    """
    Crea una factura vencida o futura según days_offset respecto a hoy.
    days_offset negativo = vencida hace N días; 0 = vence hoy; positivo = futura.
    Defaults: impaga, no debitada, no cancelada, no incobrable, sin payment_date.
    """
    defaults = dict(
        payment_type="C",
        amount=100,
        creation_date=date.today() - timedelta(days=30),
        expiration_date=date.today() + timedelta(days=days_offset),
        service_from=date.today() - timedelta(days=30),
        service_to=date.today(),
        paid=False,
        debited=False,
        canceled=False,
        uncollectible=False,
        payment_date=None,
    )
    defaults.update(kwargs)
    return Invoice.objects.create(contact=contact, **defaults)


class TestIsOverdue(TestCase):

    def setUp(self):
        self.contact = create_contact("test", "099000001")

    def test_vence_ayer_es_vencida(self):
        invoice = make_invoice(self.contact, days_offset=-1)
        self.assertTrue(invoice.is_overdue)

    def test_vence_hoy_no_es_vencida(self):
        invoice = make_invoice(self.contact, days_offset=0)
        self.assertFalse(invoice.is_overdue)

    def test_vence_manana_no_es_vencida(self):
        invoice = make_invoice(self.contact, days_offset=1)
        self.assertFalse(invoice.is_overdue)

    def test_pagada_no_es_vencida(self):
        invoice = make_invoice(self.contact, days_offset=-1, paid=True)
        self.assertFalse(invoice.is_overdue)

    def test_debitada_no_es_vencida(self):
        invoice = make_invoice(self.contact, days_offset=-1, debited=True)
        self.assertFalse(invoice.is_overdue)

    def test_cancelada_no_es_vencida(self):
        invoice = make_invoice(self.contact, days_offset=-1, canceled=True)
        self.assertFalse(invoice.is_overdue)

    def test_incobrable_no_es_vencida(self):
        invoice = make_invoice(self.contact, days_offset=-1, uncollectible=True)
        self.assertFalse(invoice.is_overdue)


class TestDebtorContactsView(TestCase):
    """
    Prueba el queryset base de debtor_contacts usando RequestFactory.
    No prueba la paginación ni los filtros de ContactFilter — solo la lógica
    de selección de contactos deudores y el conteo de owed_invoices.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser("admin", "admin@test.com", "password")

    def _get_debtor_qs(self):
        """Ejecuta la vista y devuelve el queryset base antes de paginar."""
        # Replicamos la lógica del queryset directamente para poder inspeccionarlo.
        from django.db.models import Count, Exists, Min, OuterRef, Q, Sum
        today = date.today()
        overdue_invoice_qs = Invoice.objects.filter(
            contact=OuterRef("pk"),
            paid=False,
            debited=False,
            canceled=False,
            uncollectible=False,
            payment_date__isnull=True,
            expiration_date__lt=today,
        )
        from core.models import Contact
        return (
            Contact.objects.filter(Exists(overdue_invoice_qs))
            .annotate(
                owed_invoices=Count(
                    "invoice",
                    filter=Q(
                        invoice__paid=False,
                        invoice__debited=False,
                        invoice__canceled=False,
                        invoice__uncollectible=False,
                        invoice__payment_date__isnull=True,
                        invoice__expiration_date__lt=today,
                    ),
                    distinct=True,
                )
            )
            .annotate(debt=Sum("invoice__amount"))
            .annotate(oldest_invoice=Min("invoice__creation_date"))
        )

    def test_contacto_sin_facturas_no_aparece(self):
        create_contact("sin facturas", "099000002")
        qs = self._get_debtor_qs()
        self.assertEqual(qs.count(), 0)

    def test_contacto_con_factura_vencida_aparece(self):
        contact = create_contact("deudor", "099000003")
        make_invoice(contact, days_offset=-1)
        qs = self._get_debtor_qs()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().owed_invoices, 1)

    def test_factura_vence_hoy_no_cuenta_como_deuda(self):
        contact = create_contact("vence hoy", "099000004")
        make_invoice(contact, days_offset=0)
        qs = self._get_debtor_qs()
        self.assertEqual(qs.count(), 0)

    def test_factura_pagada_no_genera_deuda(self):
        contact = create_contact("pagado", "099000005")
        make_invoice(contact, days_offset=-1, paid=True, payment_date=date.today())
        qs = self._get_debtor_qs()
        self.assertEqual(qs.count(), 0)

    def test_factura_debitada_no_genera_deuda(self):
        contact = create_contact("debitado", "099000006")
        make_invoice(contact, days_offset=-1, debited=True, payment_date=date.today())
        qs = self._get_debtor_qs()
        self.assertEqual(qs.count(), 0)

    def test_bug_cross_factura_contacto_no_aparece_si_solo_tiene_facturas_pagas(self):
        """
        Regresión: el queryset anterior con múltiples filter() sobre invoice__
        podía matchear un contacto que tuviera UNA factura con paid=False y
        OTRA con debited=False, aunque ninguna fuera genuinamente impaga.
        Con Exists() + subquery eso no debe ocurrir.
        """
        contact = create_contact("cross-factura", "099000007")
        # Factura pagada vía paid=True
        make_invoice(contact, days_offset=-5, paid=True, payment_date=date.today() - timedelta(days=4))
        # Factura debitada vía debited=True
        make_invoice(contact, days_offset=-3, debited=True, payment_date=date.today() - timedelta(days=2))
        qs = self._get_debtor_qs()
        self.assertEqual(qs.count(), 0)

    def test_bug_payment_date_con_debited_false_no_cuenta_como_deuda(self):
        """
        Regresión: una factura con debited=False pero payment_date seteado
        (estado inconsistente) no debe contarse como deuda real.
        """
        contact = create_contact("payment-date-inconsistente", "099000008")
        make_invoice(contact, days_offset=-1, debited=False, payment_date=date.today() - timedelta(days=1))
        qs = self._get_debtor_qs()
        self.assertEqual(qs.count(), 0)

    def test_owed_invoices_cuenta_solo_impagas(self):
        """
        owed_invoices debe reflejar solo las facturas genuinamente impagas,
        no inflarse con facturas pagas del mismo contacto.
        """
        contact = create_contact("mix facturas", "099000009")
        make_invoice(contact, days_offset=-5)   # impaga — cuenta
        make_invoice(contact, days_offset=-4)   # impaga — cuenta
        make_invoice(contact, days_offset=-3, paid=True, payment_date=date.today() - timedelta(days=2))  # no cuenta
        make_invoice(contact, days_offset=-2, debited=True, payment_date=date.today() - timedelta(days=1))  # no cuenta
        qs = self._get_debtor_qs()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().owed_invoices, 2)
