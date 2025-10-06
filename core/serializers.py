from rest_framework import serializers, viewsets, routers, response, status

from django.conf import settings

from .models import Address, Product, IdDocumentType
from .utils import api_log_entry


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


class ApiLogEntryViewSet(viewsets.ViewSet):
    """
    ViewSet for API log entries - only supports POST operations
    """
    authentication_classes = [] if settings.ENV_HTTP_BASIC_AUTH else viewsets.ModelViewSet.authentication_classes

    def create(self, request):
        """
        API endpoint to create a new API log entry.
        Expects JSON data with: api_id, service_id, operation_id, request_data, response_data
        """
        try:
            data = request.data
            required_fields = ['api_id', 'service_id', 'operation_id', 'request_data', 'response_data']

            # Validate required fields
            for field in required_fields:
                if field not in data:
                    return response.Response(
                        {'error': f'Missing required field: {field}'},
                        content_type="application/json",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Call the utility function to log the entry
            entry_created = api_log_entry(
                api_id=data['api_id'],
                service_id=data['service_id'],
                operation_id=data['operation_id'],
                request_data=data['request_data'],
                response_data=data['response_data'],
                caller_id=data.get('caller_id'),
                caller_detail=data.get('caller_detail'),
            )

            return response.Response(entry_created)

        except Exception as e:
            return response.Response(
                {'error': f'Failed to create API log entry: {str(e)}'},
                content_type="application/json",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


router = routers.DefaultRouter()
router.register(r'document-types', IdDocumentTypeViewSet)
router.register(r"api-log-entry", ApiLogEntryViewSet, basename="api-log-entry")
