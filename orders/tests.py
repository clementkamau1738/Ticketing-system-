from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from users.models import CustomUser
from events.models import Event
from tickets.models import Ticket, IssuedTicket
from orders.models import Order, OrderItem
from orders.views import fulfill_order
from django.utils import timezone
from django.core import mail

class OrderTests(APITestCase):
    def setUp(self):
        self.organizer = CustomUser.objects.create_user(username='organizer', password='password', role='organizer', email='organizer@example.com')
        self.attendee = CustomUser.objects.create_user(username='attendee', password='password', role='attendee', email='attendee@example.com')
        
        self.event = Event.objects.create(
            name='Test Concert',
            description='A great concert',
            date=timezone.now(),
            venue='Stadium',
            organizer=self.organizer,
            is_published=True
        )
        
        self.ticket = Ticket.objects.create(
            event=self.event,
            type='general',
            price=100.00,
            quantity_available=10
        )
        
        self.client.force_authenticate(user=self.attendee)

    def test_create_order(self):
        url = reverse('orders:orders-list')
        data = {
            'items': [
                {'ticket_id': str(self.ticket.id), 'quantity': 2}
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        
        order = Order.objects.first()
        self.assertEqual(order.total_amount, 200.00)
        
        # Check ticket sold count updated
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.quantity_sold, 2)

    def test_create_order_insufficient_stock(self):
        url = reverse('orders:orders-list')
        data = {
            'items': [
                {'ticket_id': str(self.ticket.id), 'quantity': 11}
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.quantity_sold, 0)

    def test_fulfill_order(self):
        # Manually create an order
        order = Order.objects.create(attendee=self.attendee, total_amount=200.00)
        OrderItem.objects.create(order=order, ticket=self.ticket, quantity=2)
        
        fulfill_order(order)
        
        self.assertEqual(IssuedTicket.objects.count(), 2)
        self.assertEqual(IssuedTicket.objects.filter(order=order).count(), 2)
        
        # Check QR codes generated
        for issued_ticket in IssuedTicket.objects.all():
            self.assertTrue(issued_ticket.qr_code)
            
        # Check email sent
        self.assertEqual(len(mail.outbox), 1)

    def test_cancel_order(self):
        # Create an order
        url = reverse('orders:orders-list')
        data = {
            'items': [
                {'ticket_id': str(self.ticket.id), 'quantity': 2}
            ]
        }
        response = self.client.post(url, data, format='json')
        order_id = response.data['id']
        
        # Check sold count
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.quantity_sold, 2)
        
        # Cancel order
        cancel_url = reverse('orders:orders-cancel', args=[order_id])
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check status updated
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, 'cancelled')
        
        # Check inventory restored
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.quantity_sold, 0)
