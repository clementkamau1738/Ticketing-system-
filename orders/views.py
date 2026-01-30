import stripe
import requests
import base64
from io import BytesIO
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from .models import Order, Transaction
from tickets.models import Ticket, IssuedTicket
from .serializers import OrderSerializer, TransactionSerializer
from django.core.mail import send_mail

import qrcode

# ----------------------------
# Stripe Setup
# ----------------------------
stripe.api_key = settings.STRIPE_SECRET_KEY

# ----------------------------
# M-Pesa Helpers
# ----------------------------
def get_mpesa_access_token():
    """Get OAuth token from M-Pesa Daraja API"""
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(api_url, auth=(consumer_key, consumer_secret))
    return response.json().get("access_token")


def initiate_stk_push(phone_number, amount, account_reference, transaction_desc):
    """Initiate M-Pesa STK Push"""
    access_token = get_mpesa_access_token()
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    business_short_code = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    password_str = f"{business_short_code}{passkey}{timestamp}"
    password = base64.b64encode(password_str.encode('utf-8')).decode('utf-8')

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "BusinessShortCode": business_short_code,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": business_short_code,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_desc,
    }

    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# ----------------------------
# Views
# ----------------------------
@login_required
def order_history(request):
    orders = Order.objects.filter(attendee=request.user).order_by('-created_at').prefetch_related('orderitem_set__ticket__event')
    return render(request, 'orders/order_history.html', {'orders': orders})

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, attendee=request.user)
    
    if order.status == 'pending':
        with transaction.atomic():
            order.status = 'cancelled'
            order.save()
            
            # Restore inventory
            for item in order.orderitem_set.all():
                ticket = item.ticket
                # Lock ticket for update
                ticket = Ticket.objects.select_for_update().get(id=ticket.id)
                if ticket.quantity_sold >= item.quantity:
                    ticket.quantity_sold -= item.quantity
                    ticket.save()
        
        messages.success(request, f"Order #{str(order.id)[:8]} has been cancelled.")
    elif order.status == 'paid':
        messages.warning(request, "Paid orders cannot be cancelled automatically. Please contact support.")
    
    return redirect('orders:history')

# ----------------------------
# QR Code Generator
# ----------------------------
def generate_qr(issued_ticket):
    """Generate a QR code for an issued ticket"""
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(str(issued_ticket.id))  # Use the issued ticket UUID
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    issued_ticket.qr_code.save(f"{issued_ticket.id}.png", ContentFile(buffer.getvalue()))
    issued_ticket.save()

def send_confirmation(order):
    send_mail(
        'Ticket Purchase Confirmation',
        f'Your order {order.id} is confirmed. Event: {order.tickets.first().event.name}',
        'from@example.com',
        [order.attendee.email],
        fail_silently=False,
    )

def fulfill_order(order):
    """Create issued tickets and generate QR codes"""
    # Update order status
    if order.status != 'paid':
        order.status = 'paid'
        order.save()

    # Avoid duplicate fulfillment
    if order.issued_tickets.exists():
        return

    for item in order.orderitem_set.all():
        for _ in range(item.quantity):
            issued_ticket = IssuedTicket.objects.create(
                ticket=item.ticket,
                order=order
            )
            generate_qr(issued_ticket)
    
    send_confirmation(order)


    
# ----------------------------
# Order ViewSet
# ----------------------------
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        order = serializer.save(attendee=self.request.user)
        # QR codes will be generated after successful payment

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status == 'cancelled':
             return Response({'status': 'already cancelled'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Only allow cancelling pending orders automatically for now
        if order.status == 'pending':
            with transaction.atomic():
                order.status = 'cancelled'
                order.save()
                
                # Restore inventory
                for item in order.orderitem_set.all():
                    ticket = item.ticket
                    # Lock ticket
                    ticket = Ticket.objects.select_for_update().get(id=ticket.id)
                    ticket.quantity_sold -= item.quantity
                    ticket.save()
                    
            return Response({'status': 'cancelled'})
        
        return Response({'error': 'Cannot cancel paid orders automatically'}, status=status.HTTP_400_BAD_REQUEST)

# ----------------------------
# Stripe Checkout View
# ----------------------------
class StripeCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        try:
            order = Order.objects.get(id=order_id, attendee=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': f'Tickets for Order {order.id}'},
                    'unit_amount': int(order.total_amount * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            metadata={"order_id": str(order.id)}  # Store order_id for confirmation
        )

        # Record pending transaction
        Transaction.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method="Stripe",
            status="PENDING",
            external_response=session
        )

        return Response({'checkout_session_id': session.id})

# ----------------------------
# Stripe Payment Confirmation (Webhook or Manual)
# ----------------------------
class StripePaymentConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        if not session_id:
            return Response({"error": "session_id required"}, status=400)

        session = stripe.checkout.Session.retrieve(session_id)
        order_id = session.metadata.get("order_id")
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        amount_total = session.get("amount_total")
        if amount_total is None:
            return Response({"error": "Missing amount in Stripe session"}, status=400)

        expected_amount = int(order.total_amount * 100)
        if amount_total != expected_amount:
            Transaction.objects.filter(order=order, payment_method="Stripe").update(status="FAILED")
            return Response({"error": "Amount mismatch"}, status=400)

        if order.status != 'pending':
            return Response({"error": "Order not pending"}, status=400)

        with transaction.atomic():
            Transaction.objects.filter(order=order, payment_method="Stripe").update(
                status="COMPLETED",
                payment_id=session.get("id"),
                external_response=session,
            )

            fulfill_order(order)

        return Response({"message": "Payment confirmed, QR codes generated"})

# ----------------------------
# Stripe Webhook (Secure)
# ----------------------------
class StripeWebhookView(APIView):
    """
    Handle Stripe events securely via Webhook.
    Verifies signature to prevent spoofing.
    """
    permission_classes = []  # Stripe requests are not authenticated by user
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        if not endpoint_secret:
            return Response({"error": "Webhook secret not set"}, status=400)

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            # Invalid payload
            return Response({"error": "Invalid payload"}, status=400)
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            return Response({"error": "Invalid signature"}, status=400)

        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            self.handle_checkout_session(session)

        return Response({"status": "success"})

    def handle_checkout_session(self, session):
        order_id = session.get('metadata', {}).get('order_id')
        if not order_id:
            return

        try:
            order = Order.objects.select_for_update().get(id=order_id)
        except Order.DoesNotExist:
            return

        amount_total = session.get("amount_total")
        if amount_total is None:
            return

        expected_amount = int(order.total_amount * 100)
        if amount_total != expected_amount:
            Transaction.objects.filter(order=order, payment_method="Stripe").update(status="FAILED")
            return

        if order.status != 'pending':
            return

        with transaction.atomic():
            Transaction.objects.filter(order=order, payment_method="Stripe").update(
                status="COMPLETED",
                payment_id=session.get("id"),
                external_response=session,
            )

            fulfill_order(order)

# ----------------------------
# M-Pesa Payment View
# ----------------------------
class MpesaPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        phone_number = request.data.get("phone_number")

        if not order_id or not phone_number:
            return Response({"error": "order_id and phone_number are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=order_id, attendee=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        mpesa_response = initiate_stk_push(
            phone_number=phone_number,
            amount=order.total_amount,
            account_reference=f"Order{order.id}",
            transaction_desc="Ticket Purchase"
        )

        Transaction.objects.create(
            order=order,
            amount=order.total_amount,
            phone_number=phone_number,
            payment_method="M-Pesa",
            status="PENDING",
            external_response=mpesa_response
        )

        return Response({
            "message": "Payment initiated. Please complete the payment on your phone.",
            "mpesa_response": mpesa_response
        })

# ----------------------------
# M-Pesa Callback (Webhook)
# ----------------------------
class MpesaCallbackView(APIView):
    """Handle STK Push callback to confirm payment"""
    def post(self, request):
        data = request.data
        order_id = data.get("OrderID")
        result_code = data.get("ResultCode")
        amount = data.get("Amount")

        if not order_id or result_code is None or amount is None:
            return Response({"error": "Invalid callback data"}, status=400)

        try:
            order = Order.objects.select_for_update().get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        if int(result_code) != 0:
            Transaction.objects.filter(order=order, payment_method="M-Pesa").update(status="FAILED")
            return Response({"status": "failed"})

        try:
            amount_decimal = Decimal(str(amount))
        except Exception:
            return Response({"error": "Invalid amount format"}, status=400)

        if amount_decimal != order.total_amount:
            Transaction.objects.filter(order=order, payment_method="M-Pesa").update(status="FAILED")
            return Response({"error": "Amount mismatch"}, status=400)

        if order.status != 'pending':
            return Response({"error": "Order not pending"}, status=400)

        with transaction.atomic():
            Transaction.objects.filter(order=order, payment_method="M-Pesa").update(
                status="COMPLETED",
                external_response=data,
            )

            fulfill_order(order)

        return Response({"status": "success"})
