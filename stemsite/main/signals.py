# main/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from main.email_utils import send_email_async, send_plain_email_async
from django.contrib.auth import get_user_model

from .models import (
    Assignment,
    Material,
    LiveSession,
    Timetable,
    AdminMessage,
    Notification,
    Enrollment,
)

User = get_user_model()
logger = logging.getLogger(__name__)

# -------------------------------
# HELPER — Send HTML Email
# -------------------------------
def send_student_email(to_email, subject, template_name, context):
    try:
        send_email_async(
            to_email=to_email,
            subject=subject,
            template_name=template_name,
            context=context
        )
        logger.info(f"Email queued to {to_email} with subject: {subject}")
    except Exception as e:
        logger.error(f"Email sending failed to {to_email}: {e}")


# ======================================================
# 1️⃣ ASSIGNMENT NOTIFICATION
# ======================================================
@receiver(post_save, sender=Assignment)
def notify_assignment(sender, instance, created, **kwargs):
    if not created:
        return

    enrollments = Enrollment.objects.filter(
        course=instance.course,
        is_active=True
    ).select_related("user")

    for enroll in enrollments:
        user = enroll.user
        if not user or not user.email:
            continue

        # Dashboard notification (SYNC, safe)
        Notification.objects.create(
            student=user,
            notif_type="assignment",
            title=f"New Assignment: {instance.title}",
            message=f"A new assignment '{instance.title}' was added.",
            obj_content_type=ContentType.objects.get_for_model(Assignment),
            obj_id=instance.id,
        )

        # ✅ ONLY pass JSON-safe data to Celery
        send_email_async(
            to_email=user.email,
            subject=f"New Assignment: {instance.title}",
            template_name="emails/assignment_notification.html",
            context={
                "student_name": user.get_full_name(),
                "assignment_title": instance.title,
                "course_title": instance.course.title,
                "due_date": instance.due_date,
            },
        )

# ======================================================
# 2️⃣ MATERIAL NOTIFICATION
# ======================================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.utils.timezone import localtime
from main.models import Material, Notification, Enrollment
from main.email_utils import send_email_async

User = get_user_model()


@receiver(post_save, sender=Material)
def notify_material(sender, instance, created, **kwargs):
    if not created:
        return  # Only notify on creation

    # Get all active enrolled students for the course
    enrolled_user_ids = Enrollment.objects.filter(
        course=instance.course,
        is_active=True
    ).values_list("user", flat=True)
    students = User.objects.filter(id__in=enrolled_user_ids)

    # Format Uploaded On with time
    uploaded_on = localtime(instance.uploaded_at).strftime("%A, %b %d, %Y %H:%M") \
        if instance.uploaded_at else "Not specified"

    # Instructor name (TBA since not in model)
    instructor_name = "TBA"

    for student in students:
        if not getattr(student, "email", None):
            continue

        # Dashboard notification
        Notification.objects.create(
            student=student,
            notif_type="material",
            title=f"New Material: {instance.title}",
            message=f"New learning material '{instance.title}' is available.",
            obj_content_type=ContentType.objects.get_for_model(Material),
            obj_id=instance.id,
        )

        # Email notification
        send_email_async(
            to_email=student.email,
            subject=f"New Material Added: {instance.title}",
            template_name="emails/material_notification.html",
            context={
                "student_name": student.get_full_name() if hasattr(student, "get_full_name") else str(student),
                "course_name": str(instance.course),
                "material_title": instance.title,
                "material_description": instance.description or "No description provided.",
                "uploaded_on": uploaded_on,
                "instructor_name": instructor_name,
            },
        )        

# ======================================================
# 3️⃣ LIVE SESSION NOTIFICATION
# ======================================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import localtime
from django.contrib.auth import get_user_model
from main.models import LiveSession, Notification, Enrollment
from main.email_utils import send_email_async

User = get_user_model()

@receiver(post_save, sender=LiveSession)
def notify_live_session(sender, instance, created, **kwargs):
    if not created:
        return  # only notify on creation

    # Students assigned manually
    assigned_students = instance.students.all()

    # Students enrolled in course
    enrolled_ids = Enrollment.objects.filter(course=instance.course, is_active=True).values_list("user", flat=True)
    enrolled_students = User.objects.filter(id__in=enrolled_ids)

    # Combine unique students
    students = set(list(assigned_students) + list(enrolled_students))

    # Use join_link safely
    join_link = getattr(instance, "join_link", "") or "#"

    for student in students:
        if not getattr(student, "email", None):
            continue

        # Safe student name
        student_name = student.get_full_name() if hasattr(student, "get_full_name") else str(student)

        # Dashboard notification with join link
        Notification.objects.create(
            student=student,
            notif_type="live_session",
            title=f"New Live Session: {instance.title}",
            message=(
                f"A new live session '{instance.title}' has been scheduled.\n"
                f"Click here to join: {join_link}"
            ),
            obj_content_type=ContentType.objects.get_for_model(LiveSession),
            obj_id=instance.id,
        )

        # Email notification
        send_email_async(
            to_email=student.email,
            subject=f"New Live Session Scheduled: {instance.title}",
            template_name="emails/livesession_notification.html",
            context={
                "student_name": student_name,
                "course_name": str(instance.course),
                "session_title": instance.title,
                "session_description": instance.description or "No description provided.",
                "start_time": localtime(instance.start_time).strftime("%A, %b %d, %Y %H:%M") if instance.start_time else "",
                "end_time": localtime(instance.end_time).strftime("%A, %b %d, %Y %H:%M") if instance.end_time else "Not specified",
                "join_link": join_link,
                "instructor_name": str(getattr(instance, "instructor", "")) or "TBA",
            },
        )

        

# ======================================================
# CLASS TIMETABLE / SCHEDULE NOTIFICATION
# ======================================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from main.models import Timetable, Notification
from main.email_utils import send_email_async

@receiver(post_save, sender=Timetable)
def notify_timetable(sender, instance, created, **kwargs):
    if not created:
        return

    user = instance.student
    if not user or not getattr(user, "email", None):
        return

    # 1️⃣ Dashboard notification
    Notification.objects.create(
        student=user,
        notif_type="schedule",
        title="New Class Schedule",
        message=f"A new class timetable has been added for {instance.course}.",
        obj_content_type=ContentType.objects.get_for_model(Timetable),
        obj_id=instance.id,
    )

    # 2️⃣ Email notification (JSON-safe)
    send_email_async(
        to_email=user.email,
        subject="New Class Schedule Added",
        template_name="emails/timetable_notification.html",
        context={
            "student_name": user.get_full_name() if callable(getattr(user, "get_full_name", None)) else str(user),
            "course_title": str(instance.course),
            "class_date": instance.date.strftime("%A, %b %d, %Y") if getattr(instance, "date", None) else "",
            "start_time": instance.start_time.strftime("%H:%M") if getattr(instance, "start_time", None) else "",
            "end_time": instance.end_time.strftime("%H:%M") if getattr(instance, "end_time", None) else "",
            "instructor_name": str(getattr(instance, "instructor", "")),
        },
    )



# ======================================================
# 5️⃣ ADMIN MESSAGE NOTIFICATION
# ======================================================
@receiver(post_save, sender=AdminMessage)
def notify_admin_message(sender, instance, created, **kwargs):
    if not created or instance.is_archived:
        return

    student = instance.student
    if not student or not student.email:
        return

    Notification.objects.create(
        student=student,
        notif_type="admin_msg",
        title=f"Admin Message: {instance.title}",
        message=instance.message,
        obj_content_type=ContentType.objects.get_for_model(AdminMessage),
        obj_id=instance.id,
    )

    send_email_async(
        to_email=student.email,
        subject=f"Message from Admin: {instance.title}",
        template_name="emails/admin_message_email.html",
        context={
            "title": instance.title,
            "content": instance.message,
            "student_name": student.get_full_name() or student.username,
        },
    )
    
# ======================================================
# 6️⃣ SECRET CODE GENERATION
# ======================================================
@receiver(post_save, sender=Enrollment)
def generate_secret_code(sender, instance, created, **kwargs):
    if created or instance.secret_code:
        return

    should_generate = False
    reason = ""

    if instance.is_enrollment_paid:
        should_generate = True
        reason = "Admin confirmed payment"
    elif instance.payment_method == "bank" and getattr(instance, "proof_of_payment", None):
        should_generate = True
        reason = "Bank transfer proof uploaded"

    if not should_generate:
        return

    try:
        code = instance.generate_and_set_secret_code()
    except Exception as e:
        logger.error(f"Failed to generate secret code for enrollment {instance.id}: {e}")
        return

    send_plain_email_async(
        to_email=instance.email,
        subject=f"Your STEM CodeMaster Secret Code{' (Auto)' if reason=='Bank transfer proof uploaded' else ''}",
        template_name="emails/secret_code_email.html",
        context={
            "student": instance,
            "code": code,
            "auto_continue": reason == "Bank transfer proof uploaded",
        },
    )

