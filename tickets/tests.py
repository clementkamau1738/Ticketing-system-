from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from users.models import CustomUser
from events.models import Event
from tickets.models import Ticket, IssuedTicket
from orders.models import Order
from django.utils import timezone

class TicketTests(APITestCase):
    def setUp(self):
        # Create users
        self.organizer = CustomUser.objects.create_user(username='organizer', password='password', role='organizer')
        self.attendee = CustomUser.objects.create_user(username='attendee', password='password', role='attendee')
        
        # Create event
        self.event = Event.objects.create(
            name='Test Concert',
            description='A great concert',
            date=timezone.now(),
            venue='Stadium',
            organizer=self.organizer,
            is_published=True
        )
        
        # Create ticket
        self.ticket = Ticket.objects.create(
            event=self.event,
            type='general',
            price=100.00,
            quantity_available=100
        )

    def test_ticket_str(self):
        self.assertEqual(str(self.ticket), f"{self.event.name} - {self.ticket.type}")

    def test_ticket_is_sold_out(self):
        self.assertFalse(self.ticket.is_sold_out)
        self.ticket.quantity_sold = 100
        self.ticket.save()
        self.assertTrue(self.ticket.is_sold_out)

    def test_list_tickets(self):
        url = reverse('tickets:ticket-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_ticket(self):
        self.client.force_authenticate(user=self.organizer)
        url = reverse('tickets:ticket-list')
        data = {
            'event': self.event.id,
            'type': 'vip',
            'price': 200.00,
            'quantity_available': 50
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Ticket.objects.count(), 2)

    def test_create_early_bird_ticket(self):
        self.client.force_authenticate(user=self.organizer)
        url = reverse('tickets:ticket-list')
        data = {
            'event': self.event.id,
            'type': 'early_bird',
            'price': 80.00,
            'quantity_available': 20
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Ticket.objects.get(type='early_bird').price, 80.00)

class TicketValidationTest(APITestCase):
    def setUp(self):
        self.organizer = CustomUser.objects.create_user(username='organizer', password='password', role='organizer')
        self.attendee = CustomUser.objects.create_user(username='attendee', password='password', role='attendee')
        self.hacker = CustomUser.objects.create_user(username='hacker', password='password', role='attendee')
        
        self.event = Event.objects.create(name='Event', date=timezone.now(), organizer=self.organizer)
        self.ticket = Ticket.objects.create(event=self.event, type='general', price=10, quantity_available=10)
        self.order = Order.objects.create(attendee=self.attendee, total_amount=10)
        
        self.issued_ticket = IssuedTicket.objects.create(ticket=self.ticket, order=self.order)
        self.url = reverse('tickets:issuedticket-validate', args=[self.issued_ticket.id])

    def test_validate_ticket_success(self):
        self.client.force_authenticate(user=self.organizer)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        self.issued_ticket.refresh_from_db()
        self.assertTrue(self.issued_ticket.is_redeemed)

    def test_validate_ticket_already_used(self):
        self.issued_ticket.is_redeemed = True
        self.issued_ticket.save()
        
        self.client.force_authenticate(user=self.organizer)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')

    def test_validate_ticket_unauthorized(self):
        # Create ticket for another event
        other_event = Event.objects.create(name='Other Event', date=timezone.now(), organizer=self.organizer)
        other_ticket = Ticket.objects.create(event=other_event, type='general', price=10, quantity_available=10)
        issued_ticket = IssuedTicket.objects.create(ticket=other_ticket, order=self.order)
        
        # Hacker tries to validate
        self.client.force_authenticate(user=self.hacker)
        url = reverse('tickets:issuedticket-validate', args=[issued_ticket.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
