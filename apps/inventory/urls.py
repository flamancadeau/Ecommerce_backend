from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WarehouseViewSet,
    StockViewSet,
    InboundShipmentViewSet,
    InboundItemViewSet,
)

router = DefaultRouter()
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"stocks", StockViewSet, basename="stock")
router.register(
    r"inbound-shipments", InboundShipmentViewSet, basename="inboundshipment"
)
router.register(r"inbound-items", InboundItemViewSet, basename="inbounditem")
urlpatterns = [
    path("api/v1/", include(router.urls)),
]
