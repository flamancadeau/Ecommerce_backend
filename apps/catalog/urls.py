from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet
from .views import CategoryViewSet
from .views import VariantViewSet

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"variants", VariantViewSet, basename="variant")

urlpatterns = [
    path("", include(router.urls)),
]
