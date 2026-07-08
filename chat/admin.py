from django.contrib import admin
from django.utils.html import format_html
from .models import ChatRoom, ChatMessage

# -----------------------------
# Inline messages inside a room
# -----------------------------
class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('sender', 'guest_name', 'receiver', 'content', 'timestamp')
    can_delete = False
    show_change_link = True

# -----------------------------
# ChatRoom Admin
# -----------------------------
@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'participant_list')
    inlines = [ChatMessageInline]

    def participant_list(self, obj):
        return ", ".join([user.username for user in obj.participants.all()]) or "No participants"
    participant_list.short_description = 'Participants'

# -----------------------------
# ChatMessage Admin
# -----------------------------
@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        'room',
        'display_sender',
        'receiver',
        'short_content',
        'timestamp',
        'reply_link',  # Add reply column
    )
    readonly_fields = ('room', 'sender', 'receiver', 'guest_name', 'content', 'timestamp')

    # Show "Guest" when guest sends
    def display_sender(self, obj):
        return obj.sender.username if obj.sender else (obj.guest_name or "Guest")
    display_sender.short_description = "Sender"

    # Limit message preview in list display
    def short_content(self, obj):
        return obj.content[:50] + ("..." if len(obj.content) > 50 else "")
    short_content.short_description = "Message"

    # -----------------------------------------
    # Reply button → opens admin guest chat view
    # -----------------------------------------
    def reply_link(self, obj):
        room_name = obj.room.name

    # Allow replying to BOTH guest and student chats
        if room_name.startswith("guest_") or room_name.startswith("student_"):
            url = f"/chat/admin/chat/{room_name}/"
            return format_html('<a class="button" href="{}" target="_blank">Reply</a>', url)

        return "-"
    reply_link.short_description = "Reply"
