from django.db import transaction
from rest_framework import serializers
from .models import Order, Transaction, OrderItem
from tickets.models import Ticket

class OrderItemSerializer(serializers.ModelSerializer):
    ticket_id = serializers.UUIDField()
    
    class Meta:
        model = OrderItem
        fields = ['ticket_id', 'quantity']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, write_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'attendee', 'items', 'total_amount', 'status', 'created_at']
        read_only_fields = ['id', 'attendee', 'total_amount', 'status', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        with transaction.atomic():
            order = Order.objects.create(total_amount=0, status='pending', **validated_data)
            total_amount = 0
            
            for item in items_data:
                ticket_id = item['ticket_id']
                quantity = item['quantity']
                
                try:
                    ticket = Ticket.objects.select_for_update().get(id=ticket_id)
                except Ticket.DoesNotExist:
                    raise serializers.ValidationError(f"Ticket {ticket_id} does not exist")

                if ticket.is_sold_out or (ticket.quantity_sold + quantity > ticket.quantity_available):
                    raise serializers.ValidationError(f"Not enough tickets available for {ticket.event.name} ({ticket.type})")
                
                OrderItem.objects.create(
                    order=order,
                    ticket=ticket,
                    quantity=quantity,
                    price_at_purchase=ticket.price,
                )
                
                ticket.quantity_sold += quantity
                ticket.save()
                
                total_amount += ticket.price * quantity
            
            order.total_amount = total_amount
            order.save()
            
        return order

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
