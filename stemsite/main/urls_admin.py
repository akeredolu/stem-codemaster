# urls_admin.py
from django.urls import path
from .views_admin import admin_broadcast_center

urlpatterns = [
    path('broadcast/', admin_broadcast_center, name='admin_broadcast_center'),
]

