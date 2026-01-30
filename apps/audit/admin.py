from django.contrib import admin
from django.utils.html import format_html
from .models import PriceAudit, InventoryAudit, CampaignAudit

@admin.register(PriceAudit)
class PriceAuditAdmin(admin.ModelAdmin):
    list_display = ('variant_sku', 'price_book_code', 'old_price', 'new_price', 
                    'currency', 'changed_at', 'changed_by_short')
    list_filter = ('currency', 'changed_at')
    search_fields = ('variant__sku', 'price_book__code', 'reason')
    readonly_fields = ('changed_at',)
    
    def variant_sku(self, obj):
        return obj.variant.sku if obj.variant else 'N/A'
    variant_sku.short_description = 'SKU'
    
    def price_book_code(self, obj):
        return obj.price_book.code if obj.price_book else 'N/A'
    price_book_code.short_description = 'Price Book'
    
    def changed_by_short(self, obj):
        return str(obj.changed_by)[:8] if obj.changed_by else 'System'
    changed_by_short.short_description = 'Changed By'

@admin.register(InventoryAudit)
class InventoryAuditAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'variant_sku', 'warehouse_code', 'quantity', 
                    'from_to', 'created_at', 'reference')
    list_filter = ('event_type', 'created_at', 'warehouse')
    search_fields = ('variant__sku', 'reference', 'notes')
    readonly_fields = ('created_at',)
    
    def variant_sku(self, obj):
        return obj.variant.sku
    variant_sku.short_description = 'SKU'
    
    def warehouse_code(self, obj):
        return obj.warehouse.code if obj.warehouse else 'N/A'
    warehouse_code.short_description = 'Warehouse'
    
    def from_to(self, obj):
        if obj.from_quantity is not None and obj.to_quantity is not None:
            return f"{obj.from_quantity} → {obj.to_quantity}"
        return '-'
    from_to.short_description = 'From → To'

@admin.register(CampaignAudit)
class CampaignAuditAdmin(admin.ModelAdmin):
    list_display = ('campaign_code', 'changed_field', 'old_value_preview', 
                    'new_value_preview', 'changed_at', 'changed_by_short')
    list_filter = ('changed_field', 'changed_at')
    search_fields = ('campaign__code', 'campaign__name', 'reason', 'changed_field')
    readonly_fields = ('changed_at',)
    
    def campaign_code(self, obj):
        return obj.campaign.code
    campaign_code.short_description = 'Campaign'
    
    def old_value_preview(self, obj):
        if obj.old_value and len(obj.old_value) > 30:
            return obj.old_value[:30] + '...'
        return obj.old_value or '-'
    old_value_preview.short_description = 'Old Value'
    
    def new_value_preview(self, obj):
        if obj.new_value and len(obj.new_value) > 30:
            return obj.new_value[:30] + '...'
        return obj.new_value or '-'
    new_value_preview.short_description = 'New Value'
    
    def changed_by_short(self, obj):
        return str(obj.changed_by)[:8] if obj.changed_by else 'System'
    changed_by_short.short_description = 'Changed By'