# main/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from main.utils.email_service import send_email_async
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
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        send_email_async(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            html_message=html_message,
            fail_silently=False,  # set to False for testing
        )
        logger.info(f"Email sent to {to_email} with subject: {subject}")
    except Exception as e:
        logger.error(f"Email sending failed to {to_email}: {e}")


# ======================================================
# 1️⃣ ASSIGNMENT NOTIFICATION
# ======================================================
@receiver(post_save, sender=Assignment)
def notify_assignment(sender, instance, created, **kwargs):
    if not created:
        return  # Only notify on new assignment

    enrollments = Enrollment.objects.filter(course=instance.course, is_active=True)

    for enroll in enrollments:
        user = enroll.user
        if not user or not user.email:
            continue

        # Create dashboard notification
        Notification.objects.create(
            student=user,
            notif_type="assignment",
            title=f"New Assignment: {instance.title}",
            message=f"A new assignment '{instance.title}' was added.",
            obj_content_type=ContentType.objects.get_for_model(Assignment),
            obj_id=instance.id,
        )

        # Render email and send asynchronously
        html_message = render_to_string(
            "emails/assignment_notification.html",
            {"student": user, "assignment": instance},
        )

        send_email_async(
            subject=f"New Assignment: {instance.title}",
            recipients=[user.email],
            html_message=html_message,
            fail_silently=True,  # prevents breaking if email fails
        )


# ======================================================
# 2️⃣ MATERIAL NOTIFICATION
# ======================================================
@receiver(post_save, sender=Material)
def notify_material(sender, instance, created, **kwargs):
    if not created:
        return

    enrollments = Enrollment.objects.filter(course=instance.course, is_active=True)

    for enroll in enrollments:
        user = enroll.user
        if not user or not user.email:
            continue

        Notification.objects.create(
            student=user,
            notif_type="material",
            title=f"New Material: {instance.title}",
            message=f"New learning material '{instance.title}' is available.",
            obj_content_type=ContentType.objects.get_for_model(Material),
            obj_id=instance.id,
        )

        send_email_async(
            subject=f"New Material: {instance.title}",
            recipients=[user.email],
            html_message=render_to_string(
                "emails/material_notification.html",
                {
                    "student": user,
                    "material": instance,
                },
            ),
        )

# ======================================================
# 3️⃣ LIVE SESSION NOTIFICATION
# ======================================================
@receiver(post_save, sender=LiveSession)
def notify_live_session(sender, instance, created, **kwargs):
    if not created:
        return

    assigned_students = instance.students.all()
    enrolled_students = Enrollment.objects.filter(course=instance.course).values_list("user", flat=True)

    students = set(list(assigned_students) + list(User.objects.filter(id__in=enrolled_students)))

    for student in students:
        if not student.email:
            continue

        send_email_async(
            subject=f"New Live Session: {instance.title}",
            recipients=[student.email],
            html_message=render_to_string(
                "emails/livesession_notification.html",
                {
                    "student": student,
                    "session": instance,
                },
            ),
        )

# ======================================================
# CLASS TIMETABLE NOTIFICATION
# ======================================================
@receiver(post_save, sender=Timetable)
def notify_timetable(sender, instance, created, **kwargs):
    if not created:
        return

    user = instance.student

    if not user or not user.email:
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

    # 2️⃣ Email notification
    html_message = render_to_string(
        "emails/timetable_notification.html",
        {
            "student": user,
            "timetable": instance,
        },
    )

    send_email_async(
        subject="New Class Timetable Added",
        recipients=[user.email],
        html_message=html_message,
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
        subject=f"Message from Admin: {instance.title}",
        recipients=[student.email],
        html_message=render_to_string(
            "emails/admin_message_email.html",
            {
                "title": instance.title,
                "content": instance.message,
                "student_name": student.get_full_name() or student.username,
            },
        ),
    )
    
    
# ======================================================
# CLASS SCHEDULE NOTIFICATION
# ======================================================
@receiver(post_save, sender=Timetable)
def notify_schedule(sender, instance, created, **kwargs):
    if not created:
        return

    user = instance.student

    if not user or not user.email:
        return

    # 1️⃣ Dashboard notification
    Notification.objects.create(
        student=user,
        notif_type="schedule",
        title="New Class Schedule",
        message=f"A new class schedule has been added for {instance.course}.",
        obj_content_type=ContentType.objects.get_for_model(Timetable),
        obj_id=instance.id,
    )

    # 2️⃣ Email notification
    html_message = render_to_string(
        "emails/schedule_notification.html",
        {
            "student": user,
            "timetable": instance,
        },
    )

    send_email_async(
        subject="New Class Schedule Added",
        recipients=[user.email],
        html_message=html_message,
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

    send_student_email(
        to_email=instance.email,
        subject=f"Your STEM CodeMaster Secret Code{' (Auto)' if reason=='Bank transfer proof uploaded' else ''}",
        template_name="emails/secret_code_email.html",
        context={
            "student": instance,
            "code": code,
            "auto_continue": reason == "Bank transfer proof uploaded",
        },
    )

