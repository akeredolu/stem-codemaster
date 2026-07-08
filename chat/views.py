import uuid
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import ChatRoom, ChatMessage
from chat.consumers import online_admins

User = get_user_model()


# -------------------- Helper --------------------
def _room_name_for_student(username: str) -> str:
    """Standardized room name for all students (same format as Dayo)."""
    return f"student_{username}_admin"


def _room_name_for_guest(guest_id: str) -> str:
    return f"guest_{guest_id}_admin"


def _push_to_group(room_name: str, message: str, sender_username: str, receiver_username: str):
    """Send message event to channels group so connected clients get it in realtime."""
    channel_layer = get_channel_layer()
    group_name = f"chat_{room_name}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "chat_message",   # consumer handler name
            "message": message,
            "sender": sender_username,
            "receiver": receiver_username,
            "room_name": room_name,
        }
    )


# -------------------- Guest --------------------
def guest_chat(request):
    """Guest chat page: create guest_id in session and show chat UI."""
    guest_id = request.session.get("guest_id")
    if not guest_id:
        guest_id = uuid.uuid4().hex[:8]
        request.session["guest_id"] = guest_id

    room_name = _room_name_for_guest(guest_id)
    # ensure room exists
    ChatRoom.objects.get_or_create(name=room_name)

    return render(request, "chat/chat.html", {
        "room_name": room_name,
        "sender": guest_id,
        "chat_type": "guest",
        "is_admin": False
    })


@csrf_exempt
def send_guest_message(request):
    """AJAX fallback for guest chat. Saves message and pushes to group."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        guest_name = data.get("guest_name", "Guest")
        if not message:
            return JsonResponse({"error": "Empty message"}, status=400)

        guest_id = request.session.get("guest_id")
        if not guest_id:
            # if session lost, create a new guest id (fallback)
            guest_id = uuid.uuid4().hex[:8]
            request.session["guest_id"] = guest_id

        room_name = _room_name_for_guest(guest_id)
        room, _ = ChatRoom.objects.get_or_create(name=room_name)

        # use a placeholder guest user or create one
        guest_user, _ = User.objects.get_or_create(username=f"guest_{guest_id}")
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            return JsonResponse({"error": "No admin user found"}, status=500)

        # Save using correct model fields (content + room FK)
        cm = ChatMessage.objects.create(
            room=room,
            sender=guest_user,
            receiver=admin,
            content=message,
            guest_name=guest_name
        )

        # Push realtime to channel group
        _push_to_group(room.name, message, guest_user.username, admin.username)

        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# -------------------- Student --------------------
@login_required
def student_chat(request):
    """Student chat page — uses the unified room name format (student_<username>_admin)."""
    user = request.user
    room_name = _room_name_for_student(user.username)

    # ensure room exists
    room, _ = ChatRoom.objects.get_or_create(name=room_name)

    return render(request, "chat/chat.html", {
        "room_name": room.name,
        "sender": user.username,
        "chat_type": "student",
        "is_admin": False
    })


@csrf_exempt
@login_required
def send_chat_message(request):
    """Send student → admin chat (AJAX fallback). Save to DB with correct fields and push to group."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request"})

    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        if not message:
            return JsonResponse({"success": False, "error": "Empty message"})

        user = request.user
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            return JsonResponse({"success": False, "error": "No admin found"})

        room_name = _room_name_for_student(user.username)
        room, _ = ChatRoom.objects.get_or_create(name=room_name)

        cm = ChatMessage.objects.create(
            room=room,
            sender=user,
            receiver=admin,
            content=message
        )

        # realtime push
        _push_to_group(room.name, message, user.username, admin.username)

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def load_messages(request):
    """Load all messages between the logged-in student and admin."""
    if not request.user.is_authenticated:
        return JsonResponse({"messages": []})

    user = request.user
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        return JsonResponse({"messages": []})

    # use unified room name
    room_name = _room_name_for_student(user.username)
    msgs = ChatMessage.objects.filter(
        (Q(sender=user) & Q(receiver=admin)) |
        (Q(sender=admin) & Q(receiver=user))
    ).order_by("timestamp")

    data = [{
        "sender": "student" if m.sender == user else "admin",
        "message": m.content,
        "timestamp": m.timestamp.isoformat() if getattr(m, "timestamp", None) else None
    } for m in msgs]

    return JsonResponse({"messages": data})


# -------------------- Admin --------------------
@login_required
def admin_chat(request, room_name):
    """Admin chat UI (keeps same behaviour)."""
    return render(request, "chat/admin_chat.html", {
        "room_name": room_name,
        "chat_with": room_name.replace("_admin", "")
    })


@staff_member_required
def admin_reply_chat(request, room_name):
    """
    Admin replies to student or guest. Handles GET to show messages and POST to send a reply.
    Uses correct model fields and pushes to the channels group so the student sees it realtime.
    """
    room = get_object_or_404(ChatRoom, name=room_name)
    messages = room.messages.order_by("timestamp")

    if request.method == "POST":
        # admin posting a reply from admin UI
        text = request.POST.get("message", "").strip()
        if text:
            admin_user = request.user
            # decide receiver: if room is student_<username>_admin -> student username is second segment
            receiver_username = None
            if room_name.startswith("student_") and room_name.endswith("_admin"):
                receiver_username = room_name.split("_")[1]
            elif room_name.startswith("guest_"):
                # for guest we may have guest_<id>_admin
                receiver_username = room_name.replace("guest_", "").replace("_admin", "")
            # get receiver user object if student; for guest we create/get a guest user
            receiver_user = None
            if receiver_username:
                # try to find normal user first
                try:
                    receiver_user = User.objects.get(username=receiver_username)
                except User.DoesNotExist:
                    # fallback to guest_{id} user object (if guest)
                    receiver_user, _ = User.objects.get_or_create(username=f"guest_{receiver_username}")

            # create ChatMessage using correct fields
            cm = ChatMessage.objects.create(
                room=room,
                sender=admin_user,
                receiver=receiver_user,
                content=text
            )

            # push to group so student/guest sees it instantly
            _push_to_group(room.name, text, admin_user.username, receiver_user.username if receiver_user else "")

            # after POST redirect to same page to avoid resubmission
            return redirect(request.path)

    # Mark guest messages as read (only for guest names)
    messages.filter(is_read=False, sender__username__startswith='guest').update(is_read=True)

    return render(request, "chat/admin_reply_chat.html", {
        "room": room,
        "messages": messages,
        "admin_username": request.user.username
    })


@staff_member_required
def admin_reply_guest(request, guest_id):
    """Admin reply UI for guests (GET shows messages). Sending should use admin_reply_chat POST flow."""
    room_name = _room_name_for_guest(str(guest_id))
    messages = ChatMessage.objects.filter(room__name=room_name).order_by("timestamp")
    return render(request, "chat/admin_reply_guest.html", {
        "room_name": room_name,
        "guest_id": guest_id,
        "messages": messages
    })


@staff_member_required
def admin_inbox(request):
    rooms = ChatRoom.objects.all().order_by("-id")
    return render(request, "chat/admin_inbox.html", {"rooms": rooms})


# -------------------- Admin Status --------------------
def check_admin_status(request):
    return JsonResponse({"online": len(online_admins) > 0})


@login_required
@staff_member_required
def fetch_room_messages(request, room_name):
    """
    Fetch all messages for a given room (student or guest) for admin page.
    """
    room_name = room_name.lower()  # normalize to match consumer
    room = get_object_or_404(ChatRoom, name=room_name)
    messages = room.messages.order_by("timestamp")

    data = []
    for m in messages:
        if m.sender and m.sender.username == "admin":
            sender_label = "admin"
        elif m.message_type == "student":
            sender_label = m.sender.username if m.sender else "student"
        else:
            sender_label = m.guest_name or "Guest"

        data.append({
            "sender": sender_label,
            "message": m.content,
            "timestamp": m.timestamp.strftime("%H:%M")
        })

    return JsonResponse({"messages": data})
