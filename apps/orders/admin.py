from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from decimal import Decimal
from django.db import models
from .models import Cart, CartItem, Order, OrderItem, Reservation


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("variant", "unit_price", "total_price_display", "added_at")
    fields = ("variant", "quantity", "unit_price", "total_price_display", "added_at")

    def total_price_display(self, obj):
        return format_html("<strong>€{}</strong>", format(obj.total_price, ".2f"))

    total_price_display.short_description = "Total Price"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "id_short",
        "owner_display",
        "item_count_display",
        "total_value_display",
        "created_at",
        "expires_at",
        "is_expired_display",
    )
    list_filter = ("created_at", "expires_at")
    search_fields = ("id", "session_id", "user_id")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "is_expired_display",
        "item_count_display",
        "total_value_display",
    )
    fields = (
        "id",
        "user_id",
        "session_id",
        "created_at",
        "updated_at",
        "expires_at",
        "is_expired_display",
        "item_count_display",
        "total_value_display",
    )
    inlines = [CartItemInline]

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        if search_term:
            queryset = queryset.filter(
                models.Q(id__icontains=search_term)
                | models.Q(session_id__icontains=search_term)
                | models.Q(user_id__icontains=search_term)
            )
        return queryset, use_distinct

    def id_short(self, obj):
        return str(obj.id)[:8]

    id_short.short_description = "ID"

    def owner_display(self, obj):
        if obj.user_id:
            return format_html(
                '<span style="color: green;">👤 User: {}</span>', str(obj.user_id)[:8]
            )
        elif obj.session_id:
            return format_html(
                '<span style="color: gray;">🔒 Session: {}...</span>',
                obj.session_id[:20],
            )
        return format_html('<span style="color: red;">⚠️ Anonymous</span>')

    owner_display.short_description = "Owner"

    def item_count_display(self, obj):
        count = obj.item_count
        if count == 0:
            return format_html('<span style="color: gray;">0 items</span>')
        return format_html(
            "<strong>{} item{}</strong>", count, "s" if count != 1 else ""
        )

    item_count_display.short_description = "Items"

    def total_value_display(self, obj):
        total = obj.total_value
        if total == 0:
            return format_html('<span style="color: gray;">€0.00</span>')
        return format_html(
            '<strong style="color: green;">€{}</strong>', format(total, ".2f")
        )

    total_value_display.short_description = "Total Value"

    def is_expired_display(self, obj):
        return obj.is_expired

    is_expired_display.boolean = True
    is_expired_display.short_description = "Expired"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "variant",
        "warehouse",
        "sku",
        "variant_name",
        "quantity",
        "unit_price",
        "total_price_display",
    )
    fields = (
        "variant",
        "warehouse",
        "sku",
        "variant_name",
        "quantity",
        "unit_price",
        "total_price_display",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def total_price_display(self, obj):
        return format_html("€{}", format(obj.total_price, ".2f"))

    total_price_display.short_description = "Total"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_email",
        "status_display",
        "total_display",
        "item_count_display",
        "created_at",
    )
    list_filter = ("status", "created_at", "currency")
    search_fields = ("order_number", "customer_email", "customer_id")
    readonly_fields = (
        "id",
        "order_number",
        "created_at",
        "updated_at",
        "item_count_display",
        "total_display",
    )
    fieldsets = (
        (
            "Order Information",
            {"fields": ("id", "order_number", "status", "created_at", "updated_at")},
        ),
        (
            "Customer Information",
            {
                "fields": (
                    "customer_id",
                    "customer_email",
                    "shipping_address",
                    "billing_address",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "currency",
                    "subtotal",
                    "tax_amount",
                    "shipping_amount",
                    "total",
                    "total_display",
                )
            },
        ),
        (
            "Additional Information",
            {"fields": ("item_count_display",), "classes": ("collapse",)},
        ),
    )
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
    actions = ["cancel_selected_orders"]

    def status_display(self, obj):
        colors = {
            "draft": "gray",
            "pending": "orange",
            "confirmed": "blue",
            "processing": "purple",
            "shipped": "green",
            "delivered": "darkgreen",
            "cancelled": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = "Status"

    def item_count_display(self, obj):
        count = obj.item_count
        return format_html(
            "<strong>{} item{}</strong>", count, "s" if count != 1 else ""
        )

    item_count_display.short_description = "Items"

    def total_display(self, obj):
        if obj.total is None:
            return format_html('<span style="color: gray;">€0.00</span>')
        return format_html(
            '<strong style="color: green;">€{}</strong>', format(obj.total, ".2f")
        )

    total_display.short_description = "Total"

    def cancel_selected_orders(self, request, queryset):
        cancelled_count = 0
        for order in queryset:
            if order.status in ["draft", "pending", "confirmed"]:
                order.status = "cancelled"
                order.save()
                cancelled_count += 1
        self.message_user(
            request, f"{cancelled_count} order(s) were successfully cancelled."
        )

    cancel_selected_orders.short_description = "Cancel selected orders"


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "token_short",
        "variant_sku",
        "warehouse_code",
        "quantity",
        "status_display",
        "expires_at",
        "is_expired_display",
        "order_link",
        "created_at",
    )
    list_filter = ("status", "expires_at", "warehouse", "created_at")
    search_fields = ("reservation_token", "variant__sku", "order__order_number")
    readonly_fields = (
        "id",
        "reservation_token",
        "created_at",
        "updated_at",
        "is_expired_display",
        "order_link",
    )
    fields = (
        "id",
        "reservation_token",
        "status",
        "expires_at",
        "is_expired_display",
        "variant",
        "warehouse",
        "quantity",
        "order",
        "order_link",
        "created_at",
        "updated_at",
    )

    date_hierarchy = "created_at"
    actions = ["expire_selected_reservations", "cancel_selected_reservations"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields
        else:
            return self.readonly_fields + ("reservation_token",)

    def token_short(self, obj):
        if obj.reservation_token:
            return f"{obj.reservation_token[:20]}..."
        return "-"

    token_short.short_description = "Token"

    def variant_sku(self, obj):
        return obj.variant.sku if obj.variant else "-"

    variant_sku.short_description = "SKU"

    def warehouse_code(self, obj):
        return obj.warehouse.code if obj.warehouse else "-"

    warehouse_code.short_description = "Warehouse"

    def status_display(self, obj):
        colors = {
            "pending": "orange",
            "confirmed": "green",
            "expired": "red",
            "cancelled": "darkred",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = "Status"

    def is_expired_display(self, obj):
        return obj.is_expired

    is_expired_display.boolean = True
    is_expired_display.short_description = "Expired"

    def order_link(self, obj):
        if obj.order:
            url = reverse("admin:orders_order_change", args=[obj.order.id])
            return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
        return "-"

    order_link.short_description = "Order"

    def expire_selected_reservations(self, request, queryset):
        updated = queryset.filter(status="pending").update(status="expired")
        self.message_user(request, f"{updated} reservation(s) were marked as expired.")

    expire_selected_reservations.short_description = "Expire selected reservations"

    def cancel_selected_reservations(self, request, queryset):
        updated = queryset.filter(status__in=["pending", "confirmed"]).update(
            status="cancelled"
        )
        self.message_user(request, f"{updated} reservation(s) were cancelled.")

    cancel_selected_reservations.short_description = "Cancel selected reservations"


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id_short",
        "cart_link",
        "variant_sku",
        "quantity",
        "unit_price",
        "total_price_display",
        "added_at",
    )
    search_fields = ("cart__id", "variant__sku")
    readonly_fields = (
        "id",
        "unit_price",
        "total_price_display",
        "added_at",
        "updated_at",
    )
    fields = (
        "id",
        "cart",
        "variant",
        "quantity",
        "unit_price",
        "total_price_display",
        "added_at",
        "updated_at",
    )

    def id_short(self, obj):
        return str(obj.id)[:8]

    id_short.short_description = "ID"

    def cart_link(self, obj):
        url = reverse("admin:orders_cart_change", args=[obj.cart.id])
        return format_html('<a href="{}">{}</a>', url, str(obj.cart.id)[:8])

    cart_link.short_description = "Cart"

    def variant_sku(self, obj):
        return obj.variant.sku if obj.variant else "-"

    variant_sku.short_description = "SKU"

    def total_price_display(self, obj):
        return format_html("€{}", format(obj.total_price, ".2f"))

    total_price_display.short_description = "Total"

    def save_model(self, request, obj, form, change):
        if not change or "variant" in form.changed_data:
            if obj.variant and (
                obj.unit_price == Decimal("0.00") or not obj.unit_price
            ):
                obj.unit_price = obj.variant.base_price
        super().save_model(request, obj, form, change)
