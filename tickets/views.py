from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import Ticket, IssuedTicket
from .serializers import TicketSerializer, IssuedTicketSerializer

@login_required
def my_tickets(request):
    issued_tickets = IssuedTicket.objects.filter(order__attendee=request.user).select_related('ticket__event', 'order')
    return render(request, 'tickets/my_tickets.html', {'issued_tickets': issued_tickets})

class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        event_id = self.request.query_params.get('event')
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        return queryset


class IssuedTicketViewSet(viewsets.ModelViewSet):
    queryset = IssuedTicket.objects.all()
    serializer_class = IssuedTicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Attendees see their own tickets
        if user.role == 'attendee':
            return IssuedTicket.objects.filter(order__attendee=user)
        # Organizers see tickets for their events
        elif user.role == 'organizer':
            return IssuedTicket.objects.filter(ticket__event__organizer=user)
        return IssuedTicket.objects.none()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def validate(self, request, pk=None):
        """
        Scan/Validate a ticket.
        URL: POST /api/issued_tickets/{id}/validate/
        """
        issued_ticket = self.get_object()
        
        # Check if user is authorized to validate (e.g. event organizer)
        # For simplicity, we assume any organizer can validate for now, 
        # or strictly the event organizer.
        if request.user.role != 'organizer':
             return Response({'error': 'Only organizers can validate tickets'}, status=status.HTTP_403_FORBIDDEN)
        
        if issued_ticket.ticket.event.organizer != request.user:
             return Response({'error': 'Not authorized for this event'}, status=status.HTTP_403_FORBIDDEN)

        if issued_ticket.is_redeemed:
            return Response({
                'status': 'error', 
                'message': 'Ticket already used!',
                'redeemed_at': issued_ticket.updated_at if hasattr(issued_ticket, 'updated_at') else 'Previously'
            }, status=status.HTTP_400_BAD_REQUEST)

        issued_ticket.is_redeemed = True
        issued_ticket.save()

        return Response({
            'status': 'success',
            'message': 'Ticket valid. Entry authorized.',
            'attendee': issued_ticket.order.attendee.username,
            'type': issued_ticket.ticket.type
        })
