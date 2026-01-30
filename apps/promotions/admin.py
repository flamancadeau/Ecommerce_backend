from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Campaign, CampaignRule, CampaignDiscount

class CampaignRuleInline(admin.TabularInline):
    model = CampaignRule
    extra = 1
    fields = ('rule_type', 'operator', 'value', 'scope', 'order')

class CampaignDiscountInline(admin.TabularInline):
    model = CampaignDiscount
    extra = 1
    fields = ('discount_type', 'value', 'max_discount_amount', 'min_price', 
              'min_quantity', 'max_quantity', 'applies_to')

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'start_at', 'end_at', 'priority', 'status', 
                    'usage_count', 'is_active', 'stacking_type')
    list_filter = ('is_active', 'stacking_type', 'start_at', 'end_at')
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'status', 'usage_count')
    inlines = [CampaignRuleInline, CampaignDiscountInline]
    
    def status(self, obj):
        now = timezone.now()
        if now < obj.start_at:
            color = 'blue'
            status_text = 'Scheduled'
        elif obj.start_at <= now <= obj.end_at:
            color = 'green'
            status_text = 'Active'
        else:
            color = 'gray'
            status_text = 'Expired'
        return format_html(f'<span style="color: {color}; font-weight: bold;">{status_text}</span>')
    status.short_description = 'Status'

@admin.register(CampaignRule)
class CampaignRuleAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'rule_type', 'operator', 'value_preview', 'scope', 'order')
    list_filter = ('rule_type', 'scope', 'campaign')
    search_fields = ('value', 'campaign__code', 'campaign__name')
    
    def value_preview(self, obj):
        if len(obj.value) > 50:
            return f"{obj.value[:50]}..."
        return obj.value
    value_preview.short_description = 'Value'

@admin.register(CampaignDiscount)
class CampaignDiscountAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'discount_type', 'value_display', 'min_quantity', 
                    'max_quantity', 'applies_to')
    list_filter = ('discount_type', 'applies_to', 'campaign')
    search_fields = ('campaign__code', 'campaign__name')
    
    def value_display(self, obj):
        if obj.discount_type == 'percentage':
            return f"{obj.value}%"
        elif obj.discount_type == 'fixed_amount':
            return f"€{obj.value}"
        else:
            return obj.value
    value_display.short_description = 'Value'