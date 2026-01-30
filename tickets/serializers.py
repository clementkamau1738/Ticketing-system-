from rest_framework import serializers
from .models import Ticket, IssuedTicket

class TicketSerializer(serializers.ModelSerializer):
    # Optional read-only field to check if ticket is sold out
    is_sold_out = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id',
            'event',
            'type',
            'price',
            'quantity_available',
            'is_sold_out',
        ]
        read_only_fields = ['is_sold_out']

    def get_is_sold_out(self, obj):
        return obj.is_sold_out

class IssuedTicketSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='ticket.event.name', read_only=True)
    ticket_type = serializers.CharField(source='ticket.type', read_only=True)
    attendee_name = serializers.CharField(source='order.attendee.username', read_only=True)

    class Meta:
        model = IssuedTicket
        fields = ['id', 'ticket_type', 'event_name', 'attendee_name', 'is_redeemed', 'qr_code']
