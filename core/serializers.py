from rest_framework import serializers

from core.models import Product, IdDocumentType


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class IdDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdDocumentType
        fields = "__all__"
