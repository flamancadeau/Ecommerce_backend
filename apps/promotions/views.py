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
        from .services import PromotionsService

        try:
            campaign = PromotionsService.create_campaign(
                campaign_data=request.data,
                rules_data=request.data.get("rules"),
                discounts_data=request.data.get("discounts"),
            )
            serializer = self.get_serializer(campaign)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
        from .services import PromotionsService

        is_active = request.data.get("is_active", True)
        campaign = PromotionsService.toggle_campaign_status(pk, is_active)
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=["post"], url_path="filters")
    def add_filter(self, request, pk=None):
        from .services import PromotionsService

        rule = PromotionsService.add_rule_to_campaign(pk, request.data)
        serializer = CampaignRuleSerializer(rule)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path="filters/(?P<filter_id>[^/.]+)",
    )
    def remove_filter(self, request, pk=None, filter_id=None):
        CampaignRule.objects.filter(id=filter_id, campaign_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
