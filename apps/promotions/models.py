from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from decimal import Decimal

class Campaign(models.Model):
    """Promotion campaign with time windows and rules."""
    STACKING_CHOICES = [
        ('none', 'No Stacking - Highest Priority Wins'),
        ('all', 'Stack All Eligible'),
        ('exclusive', 'Exclusive - Only This Campaign'),
        ('combined', 'Combine with Specific Campaigns'),
    ]
    
    CUSTOMER_GROUP_CHOICES = [
        ('all', 'All Customers'),
        ('new', 'New Customers Only'),
        ('returning', 'Returning Customers Only'),
        ('vip', 'VIP Customers Only'),
        ('wholesale', 'Wholesale Customers Only'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    priority = models.IntegerField(default=10, help_text="Higher number = higher priority")
    is_active = models.BooleanField(default=True)
    stacking_type = models.CharField(max_length=20, choices=STACKING_CHOICES, default='none')
    max_discount_per_order = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    customer_groups = models.JSONField(default=list, blank=True)
    excluded_customer_groups = models.JSONField(default=list, blank=True)
    usage_limit = models.IntegerField(null=True, blank=True, help_text="Maximum number of times this campaign can be used")
    usage_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'start_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['start_at', 'end_at']),
            models.Index(fields=['priority']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.code}: {self.name}"
    
    @property
    def status(self):
        from django.utils import timezone
        now = timezone.now()
        if now < self.start_at:
            return 'scheduled'
        elif self.start_at <= now <= self.end_at:
            return 'active'
        else:
            return 'expired'
    
    def is_eligible_for_customer(self, customer_context):
        """Check if campaign is eligible for given customer context."""
        if not self.customer_groups and not self.excluded_customer_groups:
            return True
        
        customer_group = customer_context.get('membership_tier', 'retail')
        
        # Check exclusions first
        if customer_group in self.excluded_customer_groups:
            return False
        
        # If specific groups are defined, check inclusion
        if self.customer_groups and customer_group not in self.customer_groups:
            return False
        
        return True

class CampaignRule(models.Model):
    """Rule defining what products/variants a campaign applies to."""
    RULE_TYPE_CHOICES = [
        ('product', 'Product'),
        ('variant', 'Variant'),
        ('category', 'Category'),
        ('brand', 'Brand'),
        ('attribute', 'Attribute'),
        ('collection', 'Collection'),
    ]
    
    OPERATOR_CHOICES = [
        ('equals', 'Equals'),
        ('not_equals', 'Not Equals'),
        ('contains', 'Contains'),
        ('not_contains', 'Not Contains'),
        ('in', 'In List'),
        ('not_in', 'Not In List'),
        ('greater_than', 'Greater Than'),
        ('less_than', 'Less Than'),
        ('between', 'Between'),
    ]
    
    SCOPE_CHOICES = [
        ('include', 'Include'),
        ('exclude', 'Exclude'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='rules')
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    operator = models.CharField(max_length=20, choices=OPERATOR_CHOICES, default='equals')
    value = models.TextField(help_text="Value to match against")
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='include')
    order = models.IntegerField(default=0, help_text="Order of evaluation")
    
    class Meta:
        ordering = ['campaign', 'order']
        indexes = [
            models.Index(fields=['campaign', 'rule_type']),
        ]
    
    def __str__(self):
        return f"{self.campaign.code}: {self.rule_type} {self.operator} {self.value[:50]}"

class CampaignDiscount(models.Model):
    """Discount definition for a campaign."""
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage Off'),
        ('fixed_amount', 'Fixed Amount Off'),
        ('price_override', 'Price Override'),
        ('tiered', 'Tiered Discount'),
        ('bogo', 'Buy X Get Y'),
    ]
    
    APPLIES_TO_CHOICES = [
        ('variant', 'Per Variant'),
        ('product', 'Per Product'),
        ('category', 'Per Category'),
        ('order', 'Entire Order'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='discounts')
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    max_quantity = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    applies_to = models.CharField(max_length=20, choices=APPLIES_TO_CHOICES, default='variant')
    tier_rules = models.JSONField(default=list, blank=True, help_text="For tiered discounts: [{'min_quantity': 5, 'discount': 10}, ...]")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['campaign', 'min_quantity']
        indexes = [
            models.Index(fields=['campaign', 'discount_type']),
        ]
    
    def __str__(self):
        return f"{self.campaign.code}: {self.get_discount_type_display()} {self.value}"
    
    def calculate_discount(self, price, quantity=1):
        """Calculate discount amount for given price and quantity."""
        if self.discount_type == 'percentage':
            discount = price * (self.value / Decimal('100'))
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        elif self.discount_type == 'fixed_amount':
            discount = self.value
        elif self.discount_type == 'price_override':
            discount = max(price - self.value, Decimal('0'))
        elif self.discount_type == 'tiered':
            discount = self._calculate_tiered_discount(price, quantity)
        else:
            discount = Decimal('0')
        
        # Apply minimum price floor
        if self.min_price:
            final_price = max(price - discount, self.min_price)
            discount = price - final_price
        
        return discount
    
    def _calculate_tiered_discount(self, price, quantity):
        """Calculate tiered discount based on quantity."""
        discount_rate = Decimal('0')
        for tier in self.tier_rules:
            if quantity >= tier.get('min_quantity', 0):
                discount_rate = max(discount_rate, Decimal(str(tier.get('discount', 0))))
        
        return price * (discount_rate / Decimal('100'))