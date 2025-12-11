# chat/models.py
from django.db import models
from django.conf import settings  # for AUTH_USER_MODEL

class ChatRoom(models.Model):
    name = models.CharField(max_length=255, unique=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True)

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="sent_messages",
        null=True,
        blank=True
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="received_messages",
        null=True,
        blank=True
    )
    content = models.TextField()
    guest_name = models.CharField(max_length=50, blank=True, null=True)  # For guest messages
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # ✅ New fields
    is_read = models.BooleanField(default=False)  # Mark messages as read
    message_type = models.CharField(
        max_length=20, 
        choices=[("guest", "Guest"), ("student", "Student"), ("admin", "Admin")], 
        default="guest"
    )

    def __str__(self):
        sender_name = self.sender.username if self.sender else self.guest_name or "Unknown"
        receiver_name = self.receiver.username if self.receiver else "Admin"
        return f"{self.room.name}: {sender_name} -> {receiver_name}"

