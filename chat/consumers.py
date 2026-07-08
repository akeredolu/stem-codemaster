import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

# Track online admins safely
online_admins = set()


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]

        # -------------------------------
        # Normalize room name (unified)
        # -------------------------------
        raw_room = self.scope["url_route"]["kwargs"]["room_name"].lower()

        # Force student_<username>_admin format for all students
        if user.is_authenticated and user.username != "admin":
            self.room_name = f"student_{user.username.lower()}_admin"
        else:
            # guests or admin connection
            self.room_name = raw_room

        self.room_group_name = f"chat_{self.room_name}"

        # Join the unified room
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Guests join the guest notification group
        if not user.is_authenticated:
            await self.channel_layer.group_add("chat_guests", self.channel_name)

        # Ensure student room exists
        if user.is_authenticated and user.username != "admin":
            from .models import ChatRoom
            room, _ = await database_sync_to_async(ChatRoom.objects.get_or_create)(
                name=self.room_name
            )
            await database_sync_to_async(lambda: room.participants.add(user))()

        await self.accept()

        # Admin online tracking
        if user.is_authenticated and user.username == "admin":
            online_admins.add(self.channel_name)

            # Notify all guests/students
            await self.channel_layer.group_send(
                "chat_guests",
                {"type": "admin_status", "online": True}
            )

        # Send current admin status
        await self.send(json.dumps({
            "type": "admin_status",
            "online": bool(online_admins)
        }))

    async def disconnect(self, close_code):
        user = self.scope["user"]

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        if not user.is_authenticated:
            await self.channel_layer.group_discard("chat_guests", self.channel_name)

        if user.is_authenticated and user.username == "admin":
            if self.channel_name in online_admins:
                online_admins.remove(self.channel_name)

            if not online_admins:
                await self.channel_layer.group_send(
                    "chat_guests",
                    {"type": "admin_status", "online": False}
                )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message")
        sender_type = data.get("sender_type")
        sender_code = data.get("sender")

        from django.contrib.auth import get_user_model
        User = get_user_model()
        from .models import ChatRoom, ChatMessage

        # -------------------------------
        # GUEST → ADMIN
        # -------------------------------
        if sender_type == "guest":
            guest_id = sender_code
            admin = await self.get_admin_user()
            room = await self.get_or_create_guest_room(guest_id)

            await self.save_message(
                room=room,
                sender=None,
                receiver=admin,
                content=message,
                guest_name=guest_id,
                message_type="guest"
            )

            await self.channel_layer.group_send(
                f"chat_{room.name}",
                {"type": "chat_message", "message": message, "sender": guest_id}
            )
            return

        # -------------------------------
        # STUDENT → ADMIN
        # -------------------------------
        if sender_type == "student":
            try:
                student = await database_sync_to_async(User.objects.get)(username=sender_code)
            except User.DoesNotExist:
                await self.send(json.dumps({"error": "Student not found"}))
                return

            admin = await self.get_admin_user()
            room = await self.get_or_create_student_room(student)

            await self.save_message(
                room=room,
                sender=student,
                receiver=admin,
                content=message,
                guest_name=None,
                message_type="student"
            )

            # Broadcast to normalized lowercase group
            await self.channel_layer.group_send(
                f"chat_{room.name.lower()}",
                {"type": "chat_message", "message": message, "sender": student.username}
            )
            return

        # -------------------------------
        # ADMIN → STUDENT/GUEST
        # -------------------------------
        if sender_type == "admin":
            admin = await self.get_admin_user()

            try:
                room = await database_sync_to_async(ChatRoom.objects.get)(name=self.room_name)
            except ChatRoom.DoesNotExist:
                await self.send(json.dumps({"error": "Room not found"}))
                return

            participants = await database_sync_to_async(
                lambda: list(room.participants.exclude(username="admin"))
            )()

            if participants:
                receiver = participants[0]
                guest_name = None
            else:
                guest_name = self.room_name.replace("_admin", "")
                receiver = None

            await self.save_message(
                room=room,
                sender=admin,
                receiver=receiver,
                content=message,
                guest_name=guest_name,
                message_type="admin"
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "message": message, "sender": "admin"}
            )

    # ==============================
    # Event Handlers
    # ==============================
    async def chat_message(self, event):
        await self.send(json.dumps({
            "type": "chat_message",
            "message": event["message"],
            "sender": event["sender"]
        }))

    async def admin_status(self, event):
        await self.send(json.dumps({
            "type": "admin_status",
            "online": event["online"]
        }))

    # ==============================
    # DB Helpers
    # ==============================
    @database_sync_to_async
    def get_admin_user(self):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.get(username="admin")

    @database_sync_to_async
    def get_or_create_guest_room(self, guest_id):
        from .models import ChatRoom
        room_name = f"{guest_id}_admin"
        return ChatRoom.objects.get_or_create(name=room_name)[0]

    @database_sync_to_async
    def get_or_create_student_room(self, student):
        from .models import ChatRoom
        room_name = f"student_{student.username}_admin".lower()
        room, _ = ChatRoom.objects.get_or_create(name=room_name)
        room.participants.add(student)
        return room

    @database_sync_to_async
    def save_message(self, room, sender, receiver, content, guest_name, message_type):
        from .models import ChatMessage
        return ChatMessage.objects.create(
            room=room,
            sender=sender,
            receiver=receiver,
            content=content,
            guest_name=guest_name,
            message_type=message_type,
            is_read=False
        )

