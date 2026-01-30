from django.db import models
from django.utils import timezone
from datetime import timedelta
from users.models import CustomUser
from tickets.models import Ticket


def default_order_expires_at():
    return timezone.now() + timedelta(minutes=15)


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('expired', 'Expired'),
    )

    attendee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    tickets = models.ManyToManyField(Ticket, through='OrderItem')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_order_expires_at)

    class Meta:
        permissions = [
            ("can_issue_refunds", "Can issue refunds"),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class Transaction(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Stripe')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    external_response = models.JSONField(blank=True, null=True)
