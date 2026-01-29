from django.db import models
from django.core.validators import MinValueValidator
import uuid
from django.utils import timezone

class Warehouse(models.Model):
    """Physical warehouse location."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2)  # ISO country code
    postal_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['country']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class Stock(models.Model):
    """Current stock level for a variant at a warehouse."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey('catalog.Variant', on_delete=models.CASCADE, related_name='stocks')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    on_hand = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    reserved = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    available = models.GeneratedField(
        expression=models.F('on_hand') - models.F('reserved'),
        output_field=models.IntegerField(),
        db_persist=True,
    )
    backorderable = models.BooleanField(default=False)
    backorder_limit = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    safety_stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['variant', 'warehouse']
        indexes = [
            models.Index(fields=['variant', 'warehouse']),
            models.Index(fields=['available']),
            models.Index(fields=['backorderable']),
        ]
    
    def __str__(self):
        return f"{self.variant.sku} at {self.warehouse.code}: {self.available} available"
    
    def can_fulfill(self, quantity):
        """Check if this stock location can fulfill requested quantity."""
        if self.available >= quantity:
            return True
        elif self.backorderable and (self.backorder_limit == 0 or quantity <= self.backorder_limit):
            return True
        return False

class InboundShipment(models.Model):
    """Expected inbound shipment from suppliers."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('arrived', 'Arrived at Warehouse'),
        ('partial', 'Partially Received'),
        ('received', 'Fully Received'),
        ('cancelled', 'Cancelled'),
        ('delayed', 'Delayed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=50, unique=True)
    supplier = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expected_at = models.DateTimeField()
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['expected_at']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['status']),
            models.Index(fields=['expected_at']),
        ]
    
    def __str__(self):
        return f"Inbound {self.reference}"
    
    @property
    def is_overdue(self):
        return self.status in ['pending', 'in_transit'] and self.expected_at < timezone.now()

class InboundItem(models.Model):
    """Items within an inbound shipment."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inbound = models.ForeignKey(InboundShipment, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey('catalog.Variant', on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    expected_quantity = models.IntegerField(validators=[MinValueValidator(1)])
    received_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['inbound', 'variant', 'warehouse']
        indexes = [
            models.Index(fields=['inbound', 'variant']),
        ]
    
    def __str__(self):
        return f"{self.variant.sku} x {self.expected_quantity} in {self.inbound.reference}"
    
    @property
    def remaining_quantity(self):
        return self.expected_quantity - self.received_quantity
    
    @property
    def is_fully_received(self):
        return self.received_quantity >= self.expected_quantity