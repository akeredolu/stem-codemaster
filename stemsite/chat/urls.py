from django.urls import path
from . import views

urlpatterns = [
    # Existing URLs
    path('guest/', views.guest_chat, name='guest_chat'),
    path('student/', views.student_chat, name='student_chat'),
    path('send_guest_message/', views.send_guest_message, name='send_guest_message'),

    # Admin pages (view + reply UI)
    path('admin/<str:room_name>/', views.admin_chat, name='admin_chat'),
    path('admin/chat/guest/<int:guest_id>/', views.admin_reply_guest, name='admin_reply_guest'),
    path('admin/chat/<str:room_name>/', views.admin_reply_chat, name='admin_reply_chat'),
    path('admin/inbox/', views.admin_inbox, name='admin_inbox'),

    # NEW required URLs for student dashboard chat tab
    path('check_admin_status/', views.check_admin_status, name='check_admin_status'),
    path('send_chat_message/', views.send_chat_message, name='send_chat_message'),
    path('load_messages/', views.load_messages, name='load_messages'),

    path('fetch_room_messages/<str:room_name>/', views.fetch_room_messages, name='fetch_room_messages'),
]

