from rest_framework import serializers
from .models import Event

class EventSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()
    organizer = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'name', 'description', 'date', 'end_date',
            'venue', 'online_link', 'organizer', 'poster',
            'is_published', 'status'
        ]
        read_only_fields = ['id', 'organizer', 'status']
