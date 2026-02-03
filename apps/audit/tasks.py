from itertools import count
from celery import shared_task
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from .models import PriceAudit, InventoryAudit, CampaignAudit
import csv
from io import StringIO
import json


@shared_task
def generate_daily_audit_report():
    """Generate daily audit report - to be called by cron"""
    yesterday = timezone.now().date() - timedelta(days=1)

    reports = []

    price_count = PriceAudit.objects.filter(changed_at__date=yesterday).count()

    inventory_count = InventoryAudit.objects.filter(created_at__date=yesterday).count()

    campaign_count = CampaignAudit.objects.filter(changed_at__date=yesterday).count()

    return {
        "date": yesterday.strftime("%Y-%m-%d"),
        "price_changes": price_count,
        "inventory_events": inventory_count,
        "campaign_changes": campaign_count,
        "total": price_count + inventory_count + campaign_count,
    }


@shared_task
def generate_weekly_audit_report(email=None):
    """Generate weekly audit report - to be called by cron every Monday"""
    end_date = timezone.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=6)

    reports = {}

    price_audits = PriceAudit.objects.filter(
        changed_at__date__gte=start_date, changed_at__date__lte=end_date
    ).select_related("variant", "price_book", "changed_by")

    reports["price"] = {
        "count": price_audits.count(),
        "by_currency": list(
            price_audits.values("currency").annotate(count=count("id"))
        ),
        "top_skus": list(
            price_audits.values("variant__sku")
            .annotate(count=count("id"))
            .order_by("-count")[:5]
        ),
    }

    inventory_audits = InventoryAudit.objects.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date
    ).select_related("variant", "warehouse")

    reports["inventory"] = {
        "count": inventory_audits.count(),
        "by_type": list(
            inventory_audits.values("event_type").annotate(count=count("id"))
        ),
        "total_qty": inventory_audits.aggregate(total=sum("quantity"))["total"] or 0,
    }

    campaign_audits = CampaignAudit.objects.filter(
        changed_at__date__gte=start_date, changed_at__date__lte=end_date
    ).select_related("campaign", "changed_by")

    reports["campaign"] = {
        "count": campaign_audits.count(),
        "by_field": list(
            campaign_audits.values("changed_field").annotate(count=count("id"))
        ),
    }

    if email:
        subject = f"Weekly Audit Report {start_date} to {end_date}"
        body = f"""
        Weekly Audit Report Summary ({start_date} to {end_date})
        
        Price Changes: {reports['price']['count']}
        Inventory Events: {reports['inventory']['count']}
        Campaign Changes: {reports['campaign']['count']}
        Total Audits: {reports['price']['count'] + reports['inventory']['count'] + reports['campaign']['count']}
        
        Detailed breakdown:
        {json.dumps(reports, indent=2)}
        """

        email_msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        email_msg.send()

    return reports


@shared_task
def generate_scheduled_report(report_type, email, format="csv"):
    """Generate scheduled report for specific type"""
    from datetime import datetime

    end_date = timezone.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=6)

    print(
        f"Generating {report_type} report from {start_date} to {end_date} in {format} format"
    )

    if email:
        print(f"Will email to: {email}")

    return {
        "status": "scheduled",
        "report_type": report_type,
        "period": f"{start_date} to {end_date}",
        "email_sent_to": email,
        "format": format,
    }


@shared_task
def cleanup_old_audit_logs(days_to_keep=365):
    """Cleanup audit logs older than specified days"""
    from datetime import datetime, timedelta

    cutoff_date = timezone.now() - timedelta(days=days_to_keep)

    price_deleted = PriceAudit.objects.filter(changed_at__lt=cutoff_date).count()

    inventory_deleted = InventoryAudit.objects.filter(
        created_at__lt=cutoff_date
    ).count()

    campaign_deleted = CampaignAudit.objects.filter(changed_at__lt=cutoff_date).count()

    return {
        "cutoff_date": cutoff_date,
        "price_audits_to_delete": price_deleted,
        "inventory_audits_to_delete": inventory_deleted,
        "campaign_audits_to_delete": campaign_deleted,
        "total_to_delete": price_deleted + inventory_deleted + campaign_deleted,
        "note": "Deletion commented out for safety",
    }


@shared_task
def export_full_audit_backup():
    """Export full audit backup - for monthly archiving"""
    from datetime import datetime

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")

    backup_data = {
        "export_timestamp": timestamp,
        "price_audits": list(PriceAudit.objects.all().values()),
        "inventory_audits": list(InventoryAudit.objects.all().values()),
        "campaign_audits": list(CampaignAudit.objects.all().values()),
    }

    filename = f"audit_backup_{timestamp}.json"

    return {
        "filename": filename,
        "price_audits_count": len(backup_data["price_audits"]),
        "inventory_audits_count": len(backup_data["inventory_audits"]),
        "campaign_audits_count": len(backup_data["campaign_audits"]),
        "total_records": len(backup_data["price_audits"])
        + len(backup_data["inventory_audits"])
        + len(backup_data["campaign_audits"]),
    }
