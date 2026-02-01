from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PriceBookViewSet, CampaignViewSet

router = DefaultRouter()
router.register(r"pricing/price-books", PriceBookViewSet, basename="price-book")
router.register(r"promotions/campaigns", CampaignViewSet, basename="campaign")

urlpatterns = [
    path("api/v1/", include(router.urls)),
]
