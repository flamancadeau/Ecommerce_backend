from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Warehouse, Stock, InboundShipment, InboundItem
from apps.catalog.models import Variant


class WarehouseSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "name",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "is_active",
            "created_at",
            "updated_at",
        ]


class StockSerializer(serializers.ModelSerializer):
    variant = serializers.PrimaryKeyRelatedField(queryset=Variant.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    variant_product = serializers.CharField(
        source="variant.product.name", read_only=True
    )
    available = serializers.IntegerField(read_only=True)

    class Meta:
        model = Stock
        fields = [
            "id",
            "variant",
            "variant_sku",
            "variant_product",
            "warehouse",
            "on_hand",
            "reserved",
            "available",
            "backorderable",
            "backorder_limit",
            "safety_stock",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        instance = getattr(self, "instance", None)

        if instance and instance.pk:
            variant = data.get("variant", instance.variant)
            warehouse = data.get("warehouse", instance.warehouse)

            if variant and warehouse:
                existing_stock = Stock.objects.filter(
                    variant=variant, warehouse=warehouse
                ).exclude(pk=instance.pk)

                if existing_stock.exists():
                    raise serializers.ValidationError(
                        {
                            "non_field_errors": [
                                "Stock for this variant at this warehouse already exists."
                            ]
                        }
                    )

        on_hand = data.get(
            "on_hand", getattr(instance, "on_hand", None) if instance else None
        )
        reserved = data.get(
            "reserved", getattr(instance, "reserved", None) if instance else None
        )

        if on_hand is not None and on_hand < 0:
            raise serializers.ValidationError(
                {"on_hand": "On hand quantity cannot be negative."}
            )

        if reserved is not None and reserved < 0:
            raise serializers.ValidationError(
                {"reserved": "Reserved quantity cannot be negative."}
            )

        if on_hand is not None and reserved is not None and reserved > on_hand:
            raise serializers.ValidationError(
                {"reserved": "Reserved quantity cannot exceed on hand quantity."}
            )

        return data

    def create(self, validated_data):
        variant = validated_data.get("variant")
        warehouse = validated_data.get("warehouse")

        try:
            existing_stock = Stock.objects.get(variant=variant, warehouse=warehouse)

            for attr, value in validated_data.items():
                setattr(existing_stock, attr, value)
            existing_stock.save()

            self.instance = existing_stock
            return existing_stock

        except Stock.DoesNotExist:
            return super().create(validated_data)


class InboundItemSerializer(serializers.ModelSerializer):
    variant = serializers.PrimaryKeyRelatedField(queryset=Variant.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    inbound = serializers.PrimaryKeyRelatedField(
        queryset=InboundShipment.objects.all(), required=True
    )
    remaining_quantity = serializers.IntegerField(read_only=True)
    is_fully_received = serializers.BooleanField(read_only=True)

    class Meta:
        model = InboundItem
        fields = [
            "id",
            "inbound",
            "variant",
            "warehouse",
            "expected_quantity",
            "received_quantity",
            "unit_cost",
            "notes",
            "remaining_quantity",
            "is_fully_received",
        ]

        validators = []

    def validate(self, data):
        inbound = data.get("inbound")
        variant = data.get("variant")
        warehouse = data.get("warehouse")

        instance = getattr(self, "instance", None)

        if instance and instance.pk:
            if inbound and variant and warehouse:
                existing = InboundItem.objects.filter(
                    inbound=inbound, variant=variant, warehouse=warehouse
                ).exclude(pk=instance.pk)

                if existing.exists():
                    raise serializers.ValidationError(
                        {
                            "non_field_errors": [
                                "Item for this variant and warehouse already exists in this shipment."
                            ]
                        }
                    )

        return data

    def validate_unit_cost(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Unit cost must be greater than zero.")
        return value

    def validate_expected_quantity(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "Expected quantity must be greater than zero."
            )
        return value

    def create(self, validated_data):

        inbound = validated_data.get("inbound")
        variant = validated_data.get("variant")
        warehouse = validated_data.get("warehouse")

        try:

            existing_item = InboundItem.objects.get(
                inbound=inbound, variant=variant, warehouse=warehouse
            )

            for attr, value in validated_data.items():
                setattr(existing_item, attr, value)
            existing_item.save()

            self.instance = existing_item
            return existing_item

        except InboundItem.DoesNotExist:

            return super().create(validated_data)


class InboundItemCreateSerializer(serializers.Serializer):

    variant = serializers.UUIDField(required=True, help_text="Product variant UUID")
    warehouse = serializers.UUIDField(required=True, help_text="Warehouse UUID")
    expected_quantity = serializers.IntegerField(
        required=True, min_value=1, help_text="Expected quantity (must be positive)"
    )
    received_quantity = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text="Received quantity (defaults to 0)",
    )
    unit_cost = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        allow_null=True,
        help_text="Unit cost (optional)",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Additional notes (optional)",
    )


class InboundShipmentWriteSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    status = serializers.CharField(default="pending", read_only=True)
    items = InboundItemCreateSerializer(many=True, required=True)

    class Meta:
        model = InboundShipment
        fields = [
            "id",
            "reference",
            "supplier",
            "status",
            "expected_at",
            "received_at",
            "notes",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("received_at",)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value

    def validate_expected_at(self, value):
        if self.instance is None:
            if isinstance(value, str):
                value = parse_datetime(value)

            if value and value < timezone.now():
                raise serializers.ValidationError(
                    "Expected date must be in the future."
                )
        return value

    def create(self, validated_data):
        items_data = validated_data.pop("items")

        with transaction.atomic():
            shipment = InboundShipment.objects.create(**validated_data)

            for item_data in items_data:
                InboundItem.objects.create(
                    inbound=shipment,
                    variant_id=item_data["variant"],
                    warehouse_id=item_data["warehouse"],
                    expected_quantity=item_data["expected_quantity"],
                    received_quantity=item_data.get("received_quantity", 0),
                    unit_cost=item_data.get("unit_cost"),
                    notes=item_data.get("notes", ""),
                )
        return shipment

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if items_data is not None:
                instance.items.all().delete()
                for item_data in items_data:
                    InboundItem.objects.create(
                        inbound=instance,
                        variant_id=item_data["variant"],
                        warehouse_id=item_data["warehouse"],
                        expected_quantity=item_data["expected_quantity"],
                        received_quantity=item_data.get("received_quantity", 0),
                        unit_cost=item_data.get("unit_cost"),
                        notes=item_data.get("notes", ""),
                    )

        return instance


class InboundShipmentSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    status = serializers.CharField(default="pending", read_only=True)
    items = InboundItemSerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = InboundShipment
        fields = [
            "id",
            "reference",
            "supplier",
            "status",
            "expected_at",
            "received_at",
            "notes",
            "items",
            "created_at",
            "updated_at",
            "is_overdue",
        ]
        read_only_fields = ("received_at",)
