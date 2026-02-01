from django.contrib import admin
from django.utils.html import format_html
from .models import Cart, CartItem, Order, OrderItem, Reservation


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("unit_price", "total_price")
    fields = ("variant", "quantity", "unit_price", "total_price")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "id_short",
        "user_or_session",
        "item_count",
        "total_value",
        "created_at",
        "is_expired",
    )
    list_filter = ("created_at", "expires_at")
    search_fields = ("session_id", "user_id")
    readonly_fields = (
        "created_at",
        "updated_at",
        "is_expired",
        "item_count",
        "total_value",
    )
    inlines = [CartItemInline]

    def id_short(self, obj):
        return str(obj.id)[:8]

    id_short.short_description = "ID"

    def user_or_session(self, obj):
        if obj.user_id:
            return f"User: {obj.user_id}"
        elif obj.session_id:
            return f"Session: {obj.session_id[:20]}..."
        return "Anonymous"

    user_or_session.short_description = "Owner"

    def item_count(self, obj):
        return obj.item_count

    item_count.short_description = "Items"

    def total_value(self, obj):
        total = sum(item.total_price for item in obj.items.all())
        return f"€{total:.2f}"

    total_value.short_description = "Total"

    def is_expired(self, obj):
        return obj.is_expired

    is_expired.boolean = True
    is_expired.short_description = "Expired"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("unit_price", "discount_amount", "tax_amount", "total_price")
    fields = (
        "variant",
        "quantity",
        "unit_price",
        "discount_amount",
        "tax_amount",
        "total_price",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_email",
        "status",
        "payment_status",
        "total",
        "created_at",
        "item_count",
    )
    list_filter = ("status", "payment_status", "created_at", "currency")
    search_fields = ("order_number", "customer_email", "customer_id")
    readonly_fields = ("created_at", "updated_at", "item_count", "total_display")
    inlines = [OrderItemInline]

    def item_count(self, obj):
        return obj.items.count()

    item_count.short_description = "Items"

    def total_display(self, obj):
        return f"€{obj.total:.2f}"

    total_display.short_description = "Total"


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "token_short",
        "variant_sku",
        "warehouse_code",
        "quantity",
        "status",
        "expires_at",
        "is_expired",
        "has_order",
    )
    list_filter = ("status", "expires_at", "warehouse")
    search_fields = ("reservation_token", "variant__sku")
    readonly_fields = ("created_at", "updated_at", "is_expired", "has_order")

    def token_short(self, obj):
        return obj.reservation_token[:20] + "..."

    token_short.short_description = "Token"

    def variant_sku(self, obj):
        return obj.variant.sku

    variant_sku.short_description = "SKU"

    def warehouse_code(self, obj):
        return obj.warehouse.code

    warehouse_code.short_description = "Warehouse"

    def is_expired(self, obj):
        return obj.is_expired

    is_expired.boolean = True
    is_expired.short_description = "Expired"

    def has_order(self, obj):
        return obj.order is not None

    has_order.boolean = True
    has_order.short_description = "Has Order"
