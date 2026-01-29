from django.contrib import admin
from django.urls import path, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.http import HttpResponse

# API schema view setup
schema_view = get_schema_view(
    openapi.Info(
        title="Ecommerce API",
        default_version='v1',
        description="API documentation for Ecommerce Backend",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

# Simple homepage view
def homepage(request):
    return HttpResponse("Welcome to the Ecommerce API!")

# URL patterns
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', homepage), 
    
    # API documentation
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
