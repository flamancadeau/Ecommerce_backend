import pytest
import logging
from django.utils import timezone
from apps.audit.models import IdempotencyKey
from apps.orders.models import Order
from apps.scheduler.serializers import IdempotencyKeySerializer

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestIdempotencyEnhanced:

    @pytest.fixture
    def sample_order(self):
        return Order.objects.create(
            order_number="ORD-TEST-999",
            customer_email="customer@example.com",
            shipping_address={},
            billing_address={},
            total="100.00",
        )

    def test_auto_hashing_and_key_generation(self):
        """Verify that system defaults (hashes/keys) are generated on save."""
        data = {
            "response_code": 200,
            "response_body": {"message": "Success", "id": 123},
            "status": "completed",
        }

        serializer = IdempotencyKeySerializer(data=data)

        assert serializer.is_valid(), f"Validation failed: {serializer.errors}"

        instance = serializer.save()

        assert instance.key is not None
        assert instance.request_hash is not None
        assert instance.expires_at > timezone.now()
        logger.info("Generated IdempotencyKey: %s", instance.key)

    def test_auto_order_linking(self, sample_order):
        """Test the heuristic that links response bodies to Order records."""
        data = {
            "key": "test-key-linking",
            "response_body": {"order_number": sample_order.order_number},
            "status": "completed",
        }

        serializer = IdempotencyKeySerializer(data=data)
        assert serializer.is_valid()
        instance = serializer.save()

        assert instance.order_id == sample_order.id
        assert instance.order.order_number == "ORD-TEST-999"

    def test_failure_on_invalid_order_reference(self):
        """
        Senior Move: Test the "Negative Path".
        What happens if the order_number doesn't exist?
        """
        data = {
            "key": "test-key-missing",
            "response_body": {"order_number": "NON-EXISTENT-ID"},
            "status": "completed",
        }

        serializer = IdempotencyKeySerializer(data=data)
        assert serializer.is_valid()
        instance = serializer.save()

        assert instance.order is None
        logger.warning("Handled missing order reference gracefully.")
