from django.db import models
from events.models import Event
import uuid


class Ticket(models.Model):
    TYPE_CHOICES = (
        ('general', 'General'),
        ('vip', 'VIP'),
        ('early_bird', 'Early Bird'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    quantity_available = models.PositiveIntegerField()
    quantity_sold = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('event', 'type')
        ordering = ['event', 'type']

    def __str__(self):
        return f"{self.event.name} - {self.type}"

    @property
    def is_sold_out(self):
        return self.quantity_sold >= self.quantity_available


class IssuedTicket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='issued_tickets')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='issued_tickets')
    qr_code = models.ImageField(upload_to='ticket_qr/', blank=True, null=True)
    is_redeemed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("can_scan_tickets", "Can scan tickets"),
        ]

    def __str__(self):
        return f"{self.ticket.event.name} - {self.ticket.type} ({self.id})"
