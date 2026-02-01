from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "pricing"

router = DefaultRouter()
router.register(r"pricebooks", views.PriceBookViewSet, basename="pricebook")
router.register(
    r"pricebook-entries", views.PriceBookEntryViewSet, basename="pricebookentry"
)
router.register(r"tax-rates", views.TaxRateViewSet, basename="taxrate")

urlpatterns = [
    path("api/v1/", include(router.urls)),
]
