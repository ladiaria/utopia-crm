from rest_framework import serializers, viewsets, routers

from core.models import Product, IdDocumentType


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class IdDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdDocumentType
        fields = "__all__"


class IdDocumentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IdDocumentType.objects.all()
    serializer_class = IdDocumentTypeSerializer


router = routers.DefaultRouter()
router.register(r'document-types', IdDocumentTypeViewSet)
