from rest_framework import serializers, viewsets, routers

from django.conf import settings

from core.models import Address, Product, IdDocumentType, Contact


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ("contact", "address_1", "city", "country", "state")


class AddressViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [] if settings.ENV_HTTP_BASIC_AUTH else viewsets.ModelViewSet.authentication_classes
    queryset = Address.objects.all()
    serializer_class = AddressSerializer


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class IdDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdDocumentType
        fields = "__all__"


class IdDocumentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [] if settings.ENV_HTTP_BASIC_AUTH else viewsets.ModelViewSet.authentication_classes
    queryset = IdDocumentType.objects.all()
    serializer_class = IdDocumentTypeSerializer


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"


class ContactViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [] if settings.ENV_HTTP_BASIC_AUTH else viewsets.ModelViewSet.authentication_classes
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer


router = routers.DefaultRouter()
router.register(r'document-types', IdDocumentTypeViewSet)
router.register(r'contacts', ContactViewSet)
