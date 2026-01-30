from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.EventListView.as_view(), name='list'),
    path('<int:event_id>/', views.event_detail, name='detail'),
    path('create/', views.event_create, name='create'),
    path('update/<int:event_id>/', views.event_update, name='update'),
    path('my-events/', views.dashboard, name='my_events'),
    path('my-events/export/<int:event_id>/', views.export_attendees, name='export_attendees'),
]
