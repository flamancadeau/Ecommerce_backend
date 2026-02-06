from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"price-books", views.PriceBookViewSet)
router.register(r"price-book-entries", views.PriceBookEntryViewSet)
router.register(r"tax-rates", views.TaxRateViewSet)

urlpatterns = [
    path("", include(router.urls)),
    # Pricing Engine endpoints
    path("quote/", views.price_quote, name="price-quote"),
    path("explain/", views.explain_price, name="explain-price"),
]
