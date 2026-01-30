from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import Order, OrderItem
from tickets.models import Ticket


@shared_task
def expire_pending_orders():
    now = timezone.now()
    orders = Order.objects.select_for_update().filter(
        status='pending',
        expires_at__lte=now,
    )

    for order in orders:
        with transaction.atomic():
            if order.status != 'pending':
                continue

            for item in OrderItem.objects.select_related('ticket').filter(order=order):
                ticket = Ticket.objects.select_for_update().get(id=item.ticket_id)
                if ticket.quantity_sold >= item.quantity:
                    ticket.quantity_sold -= item.quantity
                    ticket.save()

            order.status = 'expired'
            order.save()
