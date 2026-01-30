from django.db import models
from django.utils import timezone
from users.models import CustomUser

class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    venue = models.CharField(max_length=255, blank=True, null=True)
    online_link = models.URLField(blank=True, null=True)
    organizer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='organized_events')
    poster = models.ImageField(upload_to='event_posters/', blank=True, null=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['date'])]
        permissions = [
            ("can_create_event", "Can create event"),
            ("can_edit_own_event", "Can edit own event"),
        ]

    @property
    def status(self):
        now = timezone.now()
        if self.date > now:
            return 'Upcoming'
        elif self.end_date and self.date <= now <= self.end_date:
            return 'Ongoing'
        else:
            return 'Past'

    def __str__(self):
        return self.name