import csv
import hashlib
import json
import uuid
from io import StringIO
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .models import IdempotencyKey


class IdempotencyService:
    @staticmethod
    def generate_key():
        return str(uuid.uuid4())

    @staticmethod
    def get_request_hash(data):
        if not data:
            return ""
        request_body = json.dumps(data, sort_keys=True)
        return hashlib.sha256(request_body.encode()).hexdigest()

    @staticmethod
    def verify_or_create(key, request_path, request_data=None, expires_in_hours=24):
        """
        Main logic for idempotency check.
        Returns (idem_key, created)
        """
        request_hash = IdempotencyService.get_request_hash(request_data)

        with transaction.atomic():
            (
                idem_key,
                created,
            ) = IdempotencyKey.objects.select_for_update().get_or_create(
                key=key,
                defaults={
                    "request_path": request_path,
                    "request_hash": request_hash,
                    "status": IdempotencyKey.Status.PROCESSING,
                    "expires_at": timezone.now() + timedelta(hours=expires_in_hours),
                },
            )
            return idem_key, created

    @staticmethod
    def complete_key(key_obj, response_code, response_body):
        key_obj.status = IdempotencyKey.Status.COMPLETED
        key_obj.response_code = response_code
        key_obj.response_body = response_body
        key_obj.save()

    @staticmethod
    def mark_failed(key_obj):
        key_obj.status = IdempotencyKey.Status.FAILED
        key_obj.save()


class AuditService:
    @staticmethod
    def export_price_audits_csv(queryset):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "SKU",
                "Price Book",
                "Old Price",
                "New Price",
                "Currency",
                "Reason",
                "Changed At",
            ]
        )
        for audit in queryset:
            writer.writerow(
                [
                    audit.variant.sku if audit.variant else "N/A",
                    audit.price_book.code if audit.price_book else "N/A",
                    audit.old_price,
                    audit.new_price,
                    audit.currency,
                    audit.reason,
                    audit.changed_at,
                ]
            )
        return output.getvalue()

    @staticmethod
    def export_inventory_audits_csv(queryset):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["Event", "SKU", "Warehouse", "Qty", "From", "To", "Ref", "Date"]
        )
        for audit in queryset:
            writer.writerow(
                [
                    audit.event_type,
                    audit.variant.sku if audit.variant else "N/A",
                    audit.warehouse.code if audit.warehouse else "N/A",
                    audit.quantity,
                    audit.from_quantity,
                    audit.to_quantity,
                    audit.reference,
                    audit.created_at,
                ]
            )
        return output.getvalue()
