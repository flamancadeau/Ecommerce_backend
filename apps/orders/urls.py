from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"carts", views.CartViewSet, basename="cart")
router.register(r"orders", views.OrderViewSet, basename="order")

checkout_patterns = [
    path(
        "create-order/",
        views.CheckoutViewSet.as_view({"post": "create_order"}),
        name="create-order",
    ),
]

urlpatterns = [
    path("", include(router.urls)),
    path("checkout/", include(checkout_patterns)),
]
