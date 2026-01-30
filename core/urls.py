from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from events.views import EventViewSet, EventListView, HomeView
from tickets.views import TicketViewSet


router = DefaultRouter()
router.register(r'events', EventViewSet)
router.register(r'tickets', TicketViewSet)

urlpatterns = [
    # 🏠 Homepage (HTML)
    path('', HomeView.as_view(), name='home'),

    # 🔌 API endpoints
    path('api/', include(router.urls)),

    # 🛠 Admin
    path('admin/', admin.site.urls),

    # 🌐 Frontend pages
    path('events/', include('events.urls')),
    path('orders/', include('orders.urls')),
    path('tickets/', include('tickets.urls')),
    path('users/', include('users.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]
