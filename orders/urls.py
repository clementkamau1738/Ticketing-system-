# orders/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    OrderViewSet, 
    StripeCheckoutView, 
    StripePaymentConfirmView,
    StripeWebhookView,
    MpesaPaymentView, 
    MpesaCallbackView,
    order_history,
    cancel_order
)

# Optional: Use DRF router for OrderViewSet
router = DefaultRouter()
router.register(r'api', OrderViewSet, basename='orders')

app_name = 'orders'

urlpatterns = [
    path('history/', order_history, name='history'),
    path('cancel/<int:order_id>/', cancel_order, name='cancel'),
    path('stripe/checkout/', StripeCheckoutView.as_view(), name='stripe_checkout'),
    path('stripe/confirm/', StripePaymentConfirmView.as_view(), name='stripe_confirm'),
    path('stripe/webhook/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('mpesa/pay/', MpesaPaymentView.as_view(), name='mpesa_pay'),
    path('mpesa/callback/', MpesaCallbackView.as_view(), name='mpesa_callback'),
]

# Include router URLs for OrderViewSet
urlpatterns += router.urls
