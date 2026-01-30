from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet, IssuedTicketViewSet, my_tickets

router = DefaultRouter()
router.register(r'tickets', TicketViewSet)
router.register(r'issued_tickets', IssuedTicketViewSet)

app_name = 'tickets'

urlpatterns = [
    path('my-tickets/', my_tickets, name='my_tickets'),
    path('api/', include(router.urls)),
]
