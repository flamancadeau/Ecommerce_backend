from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from apps.audit.idempotency import idempotent_request

from .models import (
    PriceBook,
    Campaign,
    CampaignRule,
)
from apps.audit.models import CampaignAudit
from .serializers import (
    PriceBookSerializer,
    CampaignSerializer,
    CampaignRuleSerializer,
)


class PriceBookViewSet(viewsets.ModelViewSet):
    queryset = PriceBook.objects.all()
    serializer_class = PriceBookSerializer


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer

    @idempotent_request()
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @idempotent_request()
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @idempotent_request()
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        instance = serializer.save()
        CampaignAudit.objects.create(
            campaign=instance,
            changed_field="all",
            new_value="Campaign created",
            reason="Initial creation",
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        CampaignAudit.objects.create(
            campaign=instance,
            changed_field="multiple",
            new_value="Campaign updated",
            reason="Updates applied",
        )

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        now = timezone.now()

        if status_param == "active":
            qs = qs.filter(start_at__lte=now, end_at__gte=now, is_active=True)
        elif status_param == "scheduled":
            qs = qs.filter(start_at__gt=now)
        elif status_param == "expired":
            qs = qs.filter(end_at__lt=now)

        return qs

    @action(detail=True, methods=["patch"], url_path="status")
    def change_status(self, request, pk=None):
        campaign = self.get_object()
        campaign.is_active = request.data.get("is_active", True)
        campaign.save(update_fields=["is_active"])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=["post"], url_path="filters")
    def add_filter(self, request, pk=None):
        campaign = self.get_object()
        serializer = CampaignRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(campaign=campaign)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path="filters/(?P<filter_id>[^/.]+)",
    )
    def remove_filter(self, request, pk=None, filter_id=None):
        CampaignRule.objects.filter(id=filter_id, campaign_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
