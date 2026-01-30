from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Event
from .search import index_event, delete_event

@receiver(post_save, sender=Event)
def on_event_saved(sender, instance: Event, **kwargs):
    # 1. Update Search Index (Meilisearch)
    index_event(instance)
    
    # 2. Invalidate Cache
    # Always clear homepage featured events
    cache.delete('home_featured_events')
    
    # Clear event list caches (wildcard delete)
    # Note: delete_pattern is specific to django-redis
    try:
        cache.delete_pattern("events_list_*")
    except AttributeError:
        # Fallback for other backends (or if not supported)
        pass

@receiver(post_delete, sender=Event)
def on_event_deleted(sender, instance: Event, **kwargs):
    # 1. Remove from Search Index
    delete_event(instance.id)
    
    # 2. Invalidate Cache
    cache.delete('home_featured_events')
    try:
        cache.delete_pattern("events_list_*")
    except AttributeError:
        pass
