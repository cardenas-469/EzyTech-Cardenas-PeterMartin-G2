from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    stock = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0


class Order(models.Model):
    STATUS_PENDING = 'Pending'
    STATUS_CONFIRMED = 'Confirmed'
    STATUS_SHIPPED = 'Shipped'
    STATUS_COMPLETED = 'Completed'
    STATUS_CANCELLED = 'Cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    # Allowed status transitions. Terminal states cannot move again.
    ALLOWED_TRANSITIONS = {
        STATUS_PENDING: {STATUS_CONFIRMED, STATUS_CANCELLED},
        STATUS_CONFIRMED: {STATUS_SHIPPED, STATUS_CANCELLED},
        STATUS_SHIPPED: {STATUS_COMPLETED},
        STATUS_COMPLETED: set(),
        STATUS_CANCELLED: set(),
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order #{self.id} - {self.product.name}'

    @property
    def can_be_cancelled(self):
        return self.status == self.STATUS_PENDING

    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())
