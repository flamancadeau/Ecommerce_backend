from django.contrib import admin
from .models import PriceBook, PriceBookEntry, TaxRate

@admin.register(PriceBook)
class PriceBookAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'currency', 'country', 'channel', 'customer_group', 'is_active', 'is_default')
    list_filter = ('currency', 'country', 'channel', 'customer_group', 'is_active', 'is_default')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(PriceBookEntry)
class PriceBookEntryAdmin(admin.ModelAdmin):
    list_display = ('price_book', 'get_target', 'price', 'effective_from', 'effective_to', 'is_active')
    list_filter = ('price_book', 'effective_from', 'effective_to')
    search_fields = ('variant__sku', 'product__name', 'category__name')
    readonly_fields = ('created_at', 'updated_at', 'is_active')
    
    def get_target(self, obj):
        if obj.variant:
            return obj.variant.sku
        elif obj.product:
            return obj.product.name
        elif obj.category:
            return obj.category.name
        return 'N/A'
    get_target.short_description = 'Target'

@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ('country', 'state', 'tax_class', 'rate', 'is_active', 'effective_from', 'effective_to')
    list_filter = ('country', 'state', 'tax_class', 'is_active')
    search_fields = ('country', 'state')
    readonly_fields = ('created_at', 'updated_at')