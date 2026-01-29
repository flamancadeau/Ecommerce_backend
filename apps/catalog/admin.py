from django.contrib import admin
from .models import Product, Category, Variant

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'brand', 'category', 'is_active', 'launch_date')
    list_filter = ('is_active', 'brand', 'category')
    search_fields = ('name', 'slug', 'brand')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product', 'color', 'size', 'base_price', 'is_active')
    list_filter = ('is_active', 'product', 'tax_class')
    search_fields = ('sku', 'product__name')
    readonly_fields = ('created_at', 'updated_at')
    
    def color(self, obj):
        return obj.attributes.get('color', 'N/A')
    
    def size(self, obj):
        return obj.attributes.get('size', 'N/A')