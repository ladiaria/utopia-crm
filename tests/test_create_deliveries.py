# coding=utf-8
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class CreateDeliveriesVerbosityTest(TestCase):
    """
    El comando corre por cron, que manda por mail todo lo que se imprime: con --verbosity 0
    no tiene que imprimir nada, así el mail llega sólo cuando falla.
    """

    def test_verbosity_cero_no_imprime(self):
        out = StringIO()
        call_command("create_deliveries", "--verbosity", "0", stdout=out)
        self.assertEqual(out.getvalue(), "")

    def test_por_defecto_informa_el_proceso(self):
        out = StringIO()
        call_command("create_deliveries", stdout=out)
        self.assertIn("Ended process", out.getvalue())
