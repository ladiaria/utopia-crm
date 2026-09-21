from django.core import serializers
from django.test import TestCase

from support.models import IssueResolution, IssueSubcategory


class IssueSubcategoryNaturalKeyTestCase(TestCase):
    """
    IssueSubcategory defines natural_key(), so dumpdata --natural-foreign writes the FK from IssueResolution as
    [name, slug]. Without get_by_natural_key() on its manager, that fixture can be dumped but never loaded back.
    """

    def test_get_by_natural_key(self):
        subcategory = IssueSubcategory.objects.create(name="Solicitud de baja", category="S")
        self.assertEqual(IssueSubcategory.objects.get_by_natural_key(*subcategory.natural_key()), subcategory)

    def test_resolution_fixture_round_trip(self):
        subcategory = IssueSubcategory.objects.create(name="Solicitud de baja", category="S")
        IssueResolution.objects.create(subcategory=subcategory, name="Baja", slug="baja")
        dumped = serializers.serialize(
            "json", IssueResolution.objects.all(), use_natural_foreign_keys=True, use_natural_primary_keys=True
        )
        IssueResolution.objects.all().delete()

        for obj in serializers.deserialize("json", dumped):
            obj.save()

        self.assertEqual(IssueResolution.objects.get(slug="baja").subcategory, subcategory)
