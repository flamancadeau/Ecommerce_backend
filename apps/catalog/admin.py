from django.contrib import admin
from .models import Product, Category, Variant

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'brand', 'category', 'is_active', 'created_at')
    search_fields = ('name', 'slug', 'category__name')

admin.site.register(Product, ProductAdmin)
admin.site.register(Category)
admin.site.register(Variant)
