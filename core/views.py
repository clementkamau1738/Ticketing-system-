from django.shortcuts import render
from django.utils import timezone
from events.models import Event
from django.db.models import Count, Q

def home(request):
    now = timezone.now()
    
    # Featured / Trending: Upcoming published events, sorted by a simple "popularity" proxy
    # Option A: Most recently created (good for MVP)
    # Option B: Most tickets sold (better but requires Order data)
    featured_events = Event.objects.filter(
        is_published=True,
        status='upcoming',
        start_datetime__gte=now
    ).annotate(
        order_count=Count('tickets__orderitem__order', distinct=True)  # rough popularity
    ).order_by('-order_count', '-created_at')[:6]
    
    # If no orders yet, fall back to newest upcoming
    if not featured_events.exists():
        featured_events = Event.objects.filter(
            is_published=True,
            status='upcoming',
            start_datetime__gte=now
        ).order_by('-created_at')[:6]

    context = {
        'featured_events': featured_events,
        'current_location': 'Nairobi',  # Can make dynamic later via IP geolocation or user profile
    }
    return render(request, 'home.html', context)