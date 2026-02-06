from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
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
)


class PriceBookViewSet(viewsets.ModelViewSet):
    queryset = PriceBook.objects.all()
    serializer_class = PriceBookSerializer


class CampaignViewSet(viewsets.ModelViewSet):
    """
    API for managing promotional campaigns.
    Use this to retrieve campaign IDs for the scheduler.
    """

    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["start_at", "priority", "created_at"]
    ordering = ["-created_at"]

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

    def remove_filter(self, request, pk=None, filter_id=None):
        CampaignRule.objects.filter(id=filter_id, campaign_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
