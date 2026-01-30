from django.core.management.base import BaseCommand
from events.models import Event
from events.search import index_event

class Command(BaseCommand):
    help = 'Reindex all events to Meilisearch'

    def handle(self, *args, **kwargs):
        events = Event.objects.all()
        count = events.count()
        
        self.stdout.write(f'Reindexing {count} events...')
        
        for event in events:
            try:
                index_event(event)
                self.stdout.write(f'  Indexed: {event.name}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Failed: {event.name} - {e}'))
                
        self.stdout.write(self.style.SUCCESS('Reindexing completed.'))
