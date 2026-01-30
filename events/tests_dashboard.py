from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from users.models import CustomUser
from events.models import Event
from tickets.models import Ticket, IssuedTicket
from orders.models import Order, OrderItem

class DashboardTests(TestCase):
    def setUp(self):
        # Create Organizer
        self.organizer = CustomUser.objects.create_user(username='organizer', password='password', role='organizer', email='org@example.com')
        # Create Attendee
        self.attendee = CustomUser.objects.create_user(username='attendee', password='password', role='attendee', email='att@example.com')
        
        # Create Event
        self.event = Event.objects.create(
            name='Test Event',
            date=timezone.now(),
            organizer=self.organizer,
            is_published=True
        )
        
        # Create Ticket
        self.ticket = Ticket.objects.create(
            event=self.event,
            type='general',
            price=50.00,
            quantity_available=100
        )
        
        # Create Order for Attendee
        self.order = Order.objects.create(attendee=self.attendee, total_amount=100.00, status='paid')
        OrderItem.objects.create(order=self.order, ticket=self.ticket, quantity=2)
        
        # Create Issued Tickets (simulating fulfillment)
        self.issued_ticket1 = IssuedTicket.objects.create(ticket=self.ticket, order=self.order)
        self.issued_ticket2 = IssuedTicket.objects.create(ticket=self.ticket, order=self.order)

        # Manually create dummy QR codes for testing
        from django.core.files.base import ContentFile
        self.issued_ticket1.qr_code.save('test_qr.png', ContentFile(b'fakeimage'), save=True)
        self.issued_ticket2.qr_code.save('test_qr2.png', ContentFile(b'fakeimage'), save=True)
        
        # Update sales stats manually (usually handled by view/serializer)
        self.ticket.quantity_sold = 2
        self.ticket.save()

    def test_attendee_dashboard(self):
        self.client.login(username='attendee', password='password')
        response = self.client.get(reverse('tickets:my_tickets'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Event')
        self.assertContains(response, 'Download QR')
        self.assertEqual(len(response.context['issued_tickets']), 2)

    def test_order_history(self):
        self.client.login(username='attendee', password='password')
        response = self.client.get(reverse('orders:history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Event')
        self.assertContains(response, '$100.00')
        self.assertContains(response, 'Paid')

    def test_cancel_order(self):
        self.client.login(username='attendee', password='password')
        # Create a pending order
        pending_order = Order.objects.create(attendee=self.attendee, total_amount=50.00, status='pending')
        OrderItem.objects.create(order=pending_order, ticket=self.ticket, quantity=1)
        
        # Cancel it
        response = self.client.post(reverse('orders:cancel', args=[pending_order.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        
        pending_order.refresh_from_db()
        self.assertEqual(pending_order.status, 'cancelled')
        self.assertContains(response, 'Cancelled')

    def test_organizer_dashboard(self):
        self.client.login(username='organizer', password='password')
        response = self.client.get(reverse('events:my_events'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Organizer Dashboard')
        self.assertContains(response, 'Test Event')
        # Check stats
        self.assertContains(response, '2') # Tickets sold
        self.assertContains(response, '$100.00') # Revenue

    def test_csv_export(self):
        self.client.login(username='organizer', password='password')
        url = reverse('events:export_attendees', args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn('Attendee Name', content)
        self.assertIn('attendee', content)
        self.assertIn('att@example.com', content)

    def test_event_management(self):
        self.client.login(username='organizer', password='password')
        
        # Test Create Event
        response = self.client.get(reverse('events:create'))
        self.assertEqual(response.status_code, 200)
        
        from django.utils import timezone
        import datetime
        future_date = timezone.now() + datetime.timedelta(days=30)
        
        data = {
            'name': 'New Event',
            'description': 'Description',
            'date': future_date.strftime('%Y-%m-%dT%H:%M'),
            'venue': 'New Venue',
            'is_published': 'on'
        }
        
        response = self.client.post(reverse('events:create'), data, follow=True)
        self.assertContains(response, 'Event created successfully')
        self.assertTrue(Event.objects.filter(name='New Event').exists())
        
        event = Event.objects.get(name='New Event')
        
        # Test Update Event
        response = self.client.get(reverse('events:update', args=[event.id]))
        self.assertEqual(response.status_code, 200)
        
        data['name'] = 'Updated Event'
        response = self.client.post(reverse('events:update', args=[event.id]), data, follow=True)
        self.assertContains(response, 'Event updated successfully')
        
        event.refresh_from_db()
        self.assertEqual(event.name, 'Updated Event')

    def test_organizer_dashboard_access_denied(self):
        self.client.login(username='attendee', password='password')
        response = self.client.get(reverse('events:my_events'))
        self.assertEqual(response.status_code, 403)
