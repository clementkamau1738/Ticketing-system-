from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from .models import Event
from users.models import CustomUser
from tickets.models import Ticket
from datetime import timedelta

class EventModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='test_user', password='password', role='organizer')
    
    def test_status_upcoming(self):
        event = Event.objects.create(
            name='Future Event',
            description='Desc',
            date=timezone.now() + timedelta(days=1),
            organizer=self.user
        )
        self.assertEqual(event.status, 'Upcoming')

    def test_status_ongoing(self):
        now = timezone.now()
        event = Event.objects.create(
            name='Ongoing Event',
            description='Desc',
            date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            organizer=self.user
        )
        self.assertEqual(event.status, 'Ongoing')

    def test_status_past(self):
        event = Event.objects.create(
            name='Past Event',
            description='Desc',
            date=timezone.now() - timedelta(days=1),
            organizer=self.user
        )
        self.assertEqual(event.status, 'Past')


class EventAPITest(APITestCase):
    def setUp(self):
        self.organizer = CustomUser.objects.create_user(username='organizer', password='password', role='organizer')
        self.other_organizer = CustomUser.objects.create_user(username='other_org', password='password', role='organizer')
        self.attendee = CustomUser.objects.create_user(username='attendee', password='password', role='attendee')
        
        self.event_data = {
            'name': 'Test Event',
            'description': 'Description',
            'date': timezone.now() + timedelta(days=10),
            'venue': 'Venue'
        }
        # Assuming router registers 'events'
        self.list_url = reverse('event-list') 

    def test_organizer_create_event(self):
        self.client.force_authenticate(user=self.organizer)
        response = self.client.post(self.list_url, self.event_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(Event.objects.get().organizer, self.organizer)

    def test_attendee_create_event_forbidden(self):
        self.client.force_authenticate(user=self.attendee)
        response = self.client.post(self.list_url, self.event_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_event_ownership(self):
        event = Event.objects.create(organizer=self.organizer, **self.event_data)
        detail_url = reverse('event-detail', args=[event.id])
        
        # Organizer can update own
        self.client.force_authenticate(user=self.organizer)
        response = self.client.patch(detail_url, {'name': 'Updated'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Other organizer cannot update
        self.client.force_authenticate(user=self.other_organizer)
        # If unpublished, they get 404 because it's not in queryset
        response = self.client.patch(detail_url, {'name': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # If published, they get 403
        event.is_published = True
        event.save()
        response = self.client.patch(detail_url, {'name': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_publish_action(self):
        event = Event.objects.create(organizer=self.organizer, **self.event_data)
        # Using the detail route for action: events/{pk}/publish/
        url = reverse('event-publish', args=[event.id])
        
        self.client.force_authenticate(user=self.organizer)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertTrue(event.is_published)

    def test_visibility(self):
        # Published event
        Event.objects.create(organizer=self.organizer, is_published=True, name="Pub", date=timezone.now(), description="D")
        # Unpublished event
        Event.objects.create(organizer=self.organizer, is_published=False, name="Unpub", date=timezone.now(), description="D")
        
        # Anonymous user sees only published
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data), 1)
        
        # Organizer sees both (their own)
        self.client.force_authenticate(user=self.organizer)
        response = self.client.get(self.list_url)
        # Handle pagination if necessary, usually response.data['results']
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 2)


class EventListViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='org_list', password='password', role='organizer')
        self.client.login(username='org_list', password='password')
        
        # Create events
        now = timezone.now()
        
        # Future event (Published)
        self.future_event = Event.objects.create(
            name='Future Concert',
            description='Future',
            date=now + timedelta(days=10),
            venue='Stadium A',
            organizer=self.user,
            is_published=True
        )
        
        # Past event (Published)
        self.past_event = Event.objects.create(
            name='Past Concert',
            description='Past',
            date=now - timedelta(days=10),
            venue='Stadium B',
            organizer=self.user,
            is_published=True
        )
        
        # Unpublished Future event
        self.unpublished_event = Event.objects.create(
            name='Secret Concert',
            description='Secret',
            date=now + timedelta(days=10),
            venue='Stadium C',
            organizer=self.user,
            is_published=False
        )

    def test_list_shows_future_published_events_only(self):
        url = reverse('events:list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.future_event.name)
        self.assertNotContains(response, self.past_event.name)
        self.assertNotContains(response, self.unpublished_event.name)

    def test_search_filter_name(self):
        url = reverse('events:list')
        response = self.client.get(url, {'q': 'Future'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.future_event.name)
        
        response = self.client.get(url, {'q': 'NonExistent'})
        self.assertNotContains(response, self.future_event.name)

    def test_search_filter_venue(self):
        url = reverse('events:list')
        response = self.client.get(url, {'q': 'Stadium A'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.future_event.name)


    def test_date_filters(self):
        url = reverse('events:list')
        now = timezone.now()
        
        # Create event for tomorrow
        tomorrow_event = Event.objects.create(
            name='Tomorrow', date=now + timedelta(days=1), organizer=self.user, is_published=True
        )
        # Create event for next month
        next_month_event = Event.objects.create(
            name='Next Month', date=now + timedelta(days=32), organizer=self.user, is_published=True
        )

        # Test "today" (should probably be empty unless I create one for today)
        today_event = Event.objects.create(
            name='Today', date=now + timedelta(hours=1), organizer=self.user, is_published=True
        )
        
        response = self.client.get(url, {'date': 'today'})
        self.assertContains(response, today_event.name)
        self.assertNotContains(response, tomorrow_event.name)
        
        # Test "this-month"
        # Assuming now + 1 day is in this month (unless it's the last day of month)
        # Safe bet: today_event is in this month
        response = self.client.get(url, {'date': 'this-month'})
        self.assertContains(response, today_event.name)
        # next_month_event should NOT be in this month (unless strict 30 days logic, but I used calendar month)
        # If today is Jan 30, next month is March 2 (approx), so it works.
        self.assertNotContains(response, next_month_event.name)


class EventDetailViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='organizer', email='org@example.com', password='password', role='organizer'
        )
        self.event = Event.objects.create(
            name='Detail Event',
            description='Detailed Description',
            date=timezone.now() + timedelta(days=1),
            organizer=self.user,
            is_published=True,
            venue='Detail Venue'
        )

    def test_detail_view_success(self):
        url = reverse('events:detail', args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.name)
        self.assertContains(response, self.event.venue)

    def test_detail_view_unpublished_404(self):
        self.event.is_published = False
        self.event.save()
        url = reverse('events:detail', args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class HomeViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='org_home', password='password', role='organizer')
        self.now = timezone.now()
        
        # Events
        self.popular_event = Event.objects.create(
            name='Popular', date=self.now + timedelta(days=1), organizer=self.user, is_published=True
        )
        self.less_popular_event = Event.objects.create(
            name='Less Popular', date=self.now + timedelta(days=2), organizer=self.user, is_published=True
        )
        self.unpublished_event = Event.objects.create(
            name='Unpublished', date=self.now + timedelta(days=3), organizer=self.user, is_published=False
        )
        self.past_event = Event.objects.create(
            name='Past', date=self.now - timedelta(days=1), organizer=self.user, is_published=True
        )

        # Create tickets and simulate sales
        Ticket.objects.create(event=self.popular_event, type='gen', price=10, quantity_available=100, quantity_sold=50)
        Ticket.objects.create(event=self.less_popular_event, type='gen', price=10, quantity_available=100, quantity_sold=10)

    def test_home_context(self):
        url = reverse('home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        events = response.context['events']
        
        self.assertIn(self.popular_event, events)
        self.assertIn(self.less_popular_event, events)
        self.assertNotIn(self.unpublished_event, events)
        self.assertNotIn(self.past_event, events)
        
        # Check ordering (popular first)
        self.assertEqual(events[0], self.popular_event)
        self.assertEqual(events[1], self.less_popular_event)
