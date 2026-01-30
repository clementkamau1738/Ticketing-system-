from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
from django.views.generic import ListView, TemplateView
from django.db.models import Q, Sum, F
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache  # Import cache
import csv
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Event
from .serializers import EventSerializer
from .forms import EventForm
from users.permissions import IsOrganizerOrReadOnly
from .search import search_events


# ==========================
# DRF API VIEWS
# ==========================
class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer

    # Public read, organizer-only write
    permission_classes = [
        IsAuthenticatedOrReadOnly,
        IsOrganizerOrReadOnly,
    ]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'role') and user.role == 'organizer':
            # Organizers see their own events (even unpublished) and all published events
            return Event.objects.filter(Q(organizer=user) | Q(is_published=True))
        # Others see only published events
        return Event.objects.filter(is_published=True)

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsOrganizerOrReadOnly])
    def publish(self, request, pk=None):
        event = self.get_object()
        # Double check ownership (already handled by permission but good to be safe)
        if event.organizer != request.user:
             return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        
        event.is_published = True
        event.save()
        return Response({'status': 'published', 'is_published': True})

    @action(detail=True, methods=['post'], permission_classes=[IsOrganizerOrReadOnly])
    def unpublish(self, request, pk=None):
        event = self.get_object()
        if event.organizer != request.user:
             return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        event.is_published = False
        event.save()
        return Response({'status': 'unpublished', 'is_published': False})


# ==========================
# TEMPLATE-BASED VIEWS
# ==========================
class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Try to get from cache
        featured_events = cache.get('home_featured_events')
        
        if featured_events is None:
            now = timezone.now()
            # Featured events: Published, Upcoming, ordered by popularity (ticket sales)
            featured_events = list(Event.objects.filter(
                is_published=True,
                date__gte=now
            ).annotate(
                total_sales=Sum('tickets__quantity_sold')
            ).order_by('-total_sales', 'date')[:6])
            
            # Cache for 15 minutes
            cache.set('home_featured_events', featured_events, 60 * 15)
            
        context['events'] = featured_events
        return context


class EventListView(ListView):
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'
    ordering = ['date']

    def get_queryset(self):
        # Generate cache key based on GET parameters
        q = self.request.GET.get('q', '').strip().lower()
        date_filter = self.request.GET.get('date', '').strip().lower()
        
        # Unique cache key for these filters
        cache_key = f'events_list_q_{q}_date_{date_filter}'
        
        # Try fetching from cache
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            return cached_results

        queryset = super().get_queryset()
        
        # Base filter: only published events
        queryset = queryset.filter(is_published=True)
        
        # Date logic: Show upcoming events by default (or filter by date if provided)
        # Using timezone.now() to filter out past events
        now = timezone.now()
        queryset = queryset.filter(date__gte=now)

        # Advanced Date Filtering
        if date_filter == 'today':
            end_of_day = now.replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(date__lte=end_of_day)
        elif date_filter == 'this-week':
            # End of week (Sunday)
            end_of_week = now + timedelta(days=(6 - now.weekday()))
            end_of_week = end_of_week.replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(date__lte=end_of_week)
        elif date_filter == 'this-month':
            # End of month logic could be complex, simple approximation or use calendar
            # Simplified: next 30 days or strictly this month? 
            # "This month" usually means current calendar month.
            import calendar
            last_day = calendar.monthrange(now.year, now.month)[1]
            end_of_month = now.replace(day=last_day, hour=23, minute=59, second=59)
            queryset = queryset.filter(date__lte=end_of_month)
        elif date_filter == 'weekend':
            # Next Friday/Saturday/Sunday
            # If today is Friday, it includes today.
            # Calculate next Friday
            days_until_friday = (4 - now.weekday()) % 7
            next_friday = now + timedelta(days=days_until_friday)
            next_sunday = next_friday + timedelta(days=2)
            # Ensure we start from now if we are already in weekend
            start_weekend = next_friday.replace(hour=0, minute=0, second=0)
            end_weekend = next_sunday.replace(hour=23, minute=59, second=59)
            
            # If now is already in the weekend, start from now
            if now > start_weekend:
                start_weekend = now
            
            queryset = queryset.filter(date__range=[start_weekend, end_weekend])

        # Search query (q)
        if q:
            # Try Meilisearch first
            ms_ids = search_events(q)
            if ms_ids:
                queryset = queryset.filter(id__in=ms_ids)
            else:
                # Fallback to DB search
                queryset = queryset.filter(
                    Q(name__icontains=q) | 
                    Q(venue__icontains=q)
                )
            
        # Evaluate and cache
        results = list(queryset)
        cache.set(cache_key, results, 60 * 5) # Cache for 5 mins
        return results


def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id, is_published=True)
    return render(request, 'events/event_detail.html', {'event': event})


@login_required
def event_create(request):
    if request.user.role != 'organizer':
        return render(request, 'events/unauthorized.html', status=403)
        
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()
            messages.success(request, 'Event created successfully!')
            return redirect('events:my_events')
    else:
        form = EventForm()
        
    return render(request, 'events/event_form.html', {'form': form, 'title': 'Create Event'})


@login_required
def event_update(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    # Ensure user is the organizer
    if request.user != event.organizer:
        return render(request, 'events/unauthorized.html', status=403)
        
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully!')
            return redirect('events:my_events')
    else:
        form = EventForm(instance=event)
        
    return render(request, 'events/event_form.html', {'form': form, 'title': 'Edit Event', 'event': event})


@login_required
def dashboard(request):
    """Organizer Dashboard"""
    if request.user.role != 'organizer':
        return render(request, 'events/unauthorized.html', status=403)

    events = Event.objects.filter(organizer=request.user).annotate(
        total_tickets_sold=Sum('tickets__quantity_sold'),
        revenue=Sum(F('tickets__quantity_sold') * F('tickets__price'))
    ).order_by('-date')

    # Calculate aggregate stats
    total_events = events.count()
    total_sales = sum(e.total_tickets_sold or 0 for e in events)
    total_revenue = sum(e.revenue or 0 for e in events)

    context = {
        'events': events,
        'total_events': total_events,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
    }
    return render(request, 'events/dashboard.html', context)


@login_required
def export_attendees(request, event_id):
    """Export attendees list to CSV"""
    event = get_object_or_404(Event, id=event_id, organizer=request.user)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{event.name}_attendees.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Order ID', 'Attendee Name', 'Email', 'Ticket Type', 'Purchase Date', 'Checked In'])
    
    # Efficiently fetch tickets
    issued_tickets = event.tickets.all().values_list('issued_tickets__id', flat=True)
    # This is a bit complex due to reverse relation. Better to go from IssuedTicket
    from tickets.models import IssuedTicket
    
    tickets = IssuedTicket.objects.filter(ticket__event=event).select_related('order__attendee', 'ticket')
    
    for ticket in tickets:
        writer.writerow([
            ticket.order.id,
            ticket.order.attendee.username,
            ticket.order.attendee.email,
            ticket.ticket.type,
            ticket.created_at.strftime('%Y-%m-%d %H:%M'),
            'Yes' if ticket.is_redeemed else 'No'
        ])
        
    return response
