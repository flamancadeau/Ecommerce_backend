from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PriceAuditViewSet, InventoryAuditViewSet, CampaignAuditViewSet

router = DefaultRouter()
router.register(r"price-audits", PriceAuditViewSet, basename="price-audit")
router.register(r"inventory-audits", InventoryAuditViewSet, basename="inventory-audit")
router.register(r"campaign-audits", CampaignAuditViewSet, basename="campaign-audit")

urlpatterns = [
    path("", include(router.urls)),
]
