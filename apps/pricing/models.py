from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from decimal import Decimal

class PriceBook(models.Model):
    """Price book for different channels/countries/customer segments."""
    CHANNEL_CHOICES = [
        ('web', 'Web'),
        ('app', 'Mobile App'),
        ('marketplace', 'Marketplace'),
        ('retail', 'Retail Store'),
        ('wholesale', 'Wholesale'),
    ]
    
    CUSTOMER_GROUP_CHOICES = [
        ('retail', 'Retail'),
        ('wholesale', 'Wholesale'),
        ('vip', 'VIP'),
        ('employee', 'Employee'),
        ('b2b', 'B2B'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default='EUR')
    country = models.CharField(max_length=2, blank=True, help_text="ISO country code")
    channel = models.CharField(max_length=50, choices=CHANNEL_CHOICES, blank=True)
    customer_group = models.CharField(max_length=50, choices=CUSTOMER_GROUP_CHOICES, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['country', 'channel', 'customer_group']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['country', 'channel', 'customer_group']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_default']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.currency})"

class PriceBookEntry(models.Model):
    """Price for a specific variant in a price book."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    price_book = models.ForeignKey(PriceBook, on_delete=models.CASCADE, related_name='entries')
    variant = models.ForeignKey('catalog.Variant', on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey('catalog.Category', on_delete=models.CASCADE, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    min_quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    max_quantity = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Price book entries'
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['price_book', 'variant']),
            models.Index(fields=['price_book', 'product']),
            models.Index(fields=['price_book', 'category']),
            models.Index(fields=['effective_from', 'effective_to']),
            models.Index(fields=['price']),
        ]
    
    def __str__(self):
        if self.variant:
            target = self.variant.sku
        elif self.product:
            target = self.product.name
        else:
            target = self.category.name
        return f"{self.price_book.code}: {target} @ {self.price}"
    
    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        if self.effective_from and self.effective_from > now:
            return False
        if self.effective_to and self.effective_to < now:
            return False
        return True

class TaxRate(models.Model):
    """Tax rates by country/region."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.CharField(max_length=2)
    state = models.CharField(max_length=50, blank=True)
    rate = models.DecimalField(max_digits=5, decimal_places=3, validators=[MinValueValidator(0), MaxValueValidator(1)])
    tax_class = models.CharField(max_length=50, default='standard')
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['country', 'state', '-effective_from']
        unique_together = ['country', 'state', 'tax_class', 'effective_from']
        indexes = [
            models.Index(fields=['country', 'state', 'tax_class']),
            models.Index(fields=['is_active']),
            models.Index(fields=['effective_from', 'effective_to']),
        ]
    
    def __str__(self):
        state_str = f" - {self.state}" if self.state else ""
        return f"{self.country}{state_str}: {self.rate * 100}% ({self.tax_class})"