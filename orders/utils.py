from django.core.mail import send_mail

def send_confirmation_email(order):
    """Send ticket purchase confirmation email to attendee"""
    if not order.tickets.exists():
        return

    event = order.tickets.first().event
    message = f"""
    Hi {order.attendee.username},

    Your order #{order.id} has been successfully confirmed.
    
    Event: {event.title}
    Date: {event.date}
    Venue: {event.venue}

    Thank you for your purchase!
    """

    send_mail(
        subject='Ticket Purchase Confirmation',
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.attendee.email],
        fail_silently=False,
    )
