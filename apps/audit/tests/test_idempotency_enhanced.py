import pytest
from apps.audit.models import IdempotencyKey
from apps.scheduler.serializers import IdempotencyKeySerializer
from apps.orders.models import Order
from django.utils import timezone


@pytest.mark.django_db
class TestIdempotencyEnhanced:
    def test_auto_hashing_and_key_generation(self):
        """Test that missing keys and hashes are auto-generated."""
        data = {
            "response_code": 200,
            "response_body": {"message": "Success", "id": 123},
            "status": "completed",
        }

        serializer = IdempotencyKeySerializer(data=data)
        if not serializer.is_valid():
            print(f"Serializer errors: {serializer.errors}")
        assert serializer.is_valid()
        instance = serializer.save()

        assert instance.key is not None
        assert instance.request_hash is not None
        assert instance.expires_at is not None
        assert instance.expires_at > timezone.now()

    def test_auto_order_linking(self):
        """Test that the system automatically links an IdempotencyKey to an Order if ID is found."""
        # Create a real Order first
        order = Order.objects.create(
            order_number="ORD-TEST-999",
            customer_email="customer@example.com",
            shipping_address={},
            billing_address={},
            total="100.00",
        )

        # Post a result that references this order_number in the body
        data = {
            "key": "test-key-linking",
            "response_code": 201,
            "response_body": {"order_number": "ORD-TEST-999", "status": "created"},
            "status": "completed",
        }

        serializer = IdempotencyKeySerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()

        assert instance.order == order
        assert instance.order.order_number == "ORD-TEST-999"

    def test_order_linking_by_order_id_field(self):
        """Test linking when the key in body is 'order_id'."""
        order = Order.objects.create(
            order_number="ORD-ID-555",
            customer_email="customer2@example.com",
            shipping_address={},
            billing_address={},
            total="50.00",
        )

        data = {
            "key": "test-key-linking-id",
            "response_body": {"order_id": "ORD-ID-555"},
            "status": "completed",
        }

        serializer = IdempotencyKeySerializer(data=data)
        assert serializer.is_valid()
        instance = serializer.save()

        assert instance.order == order
