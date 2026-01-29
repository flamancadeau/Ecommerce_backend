from django.contrib import admin
from .models import Warehouse, Stock, InboundShipment, InboundItem

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'country', 'city', 'is_active')
    list_filter = ('country', 'is_active')
    search_fields = ('code', 'name', 'city')

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('variant', 'warehouse', 'on_hand', 'reserved', 'available', 'backorderable')
    list_filter = ('warehouse', 'backorderable')
    search_fields = ('variant__sku', 'variant__product__name')
    readonly_fields = ('available', 'created_at', 'updated_at')

class InboundItemInline(admin.TabularInline):
    model = InboundItem
    extra = 1
    readonly_fields = ('remaining_quantity', 'is_fully_received')

@admin.register(InboundShipment)
class InboundShipmentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'status', 'expected_at', 'received_at', 'is_overdue')
    list_filter = ('status', 'expected_at')
    search_fields = ('reference', 'supplier')
    inlines = [InboundItemInline]
    readonly_fields = ('created_at', 'updated_at', 'is_overdue')