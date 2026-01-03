# main/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import localtime
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

from .models import (
    Assignment,
    Material,
    LiveSession,
    Timetable,
    AdminMessage,
    Notification,
    Enrollment,
    GlobalTimetable,
)
from main.brevo_email import send_brevo_email  # ✅ Our existing Brevo helper

User = get_user_model()
logger = logging.getLogger(__name__)


# -------------------------------
# HELPER — Send Email via Brevo
# -------------------------------
def send_student_email(to_email, subject, template_name=None, context=None):
    """
    Render the template and send email via Brevo.
    template_name: template filename without .html in main/templates/emails/
    """
    try:
        html_content = None
        if template_name:
            html_content = render_to_string(f"emails/{template_name}.html", context or {})

        send_brevo_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content
        )
        logger.info(f"[EMAIL SENT ✅] To: {to_email} | Subject: {subject} | Template: {template_name or 'N/A'}")
    except Exception as e:
        logger.error(f"[EMAIL FAILED ❌] To: {to_email} | Subject: {subject} | Template: {template_name or 'N/A'} | Error: {e}")


# ======================================================
# 1️⃣ ASSIGNMENT NOTIFICATION
# ======================================================
@receiver(post_save, sender=Assignment)
def notify_assignment(sender, instance, created, **kwargs):
    if not created:
        return

    enrollments = Enrollment.objects.filter(course=instance.course, is_active=True).select_related("user")
    for enroll in enrollments:
        user = enroll.user
        if not user or not getattr(user, "email", None):
            continue

        # Dashboard notification
        Notification.objects.create(
            student=user,
            notif_type="assignment",
            title=f"New Assignment: {instance.title}",
            message=f"A new assignment '{instance.title}' was added.",
            obj_content_type=ContentType.objects.get_for_model(Assignment),
            obj_id=instance.id,
        )

        # Brevo HTML email
        send_student_email(
            to_email=user.email,
            subject=f"New Assignment: {instance.title}",
            template_name="assignment_notification",
            context={
                "student_name": user.get_full_name() or user.username,
                "assignment_title": instance.title,
                "course_title": str(instance.course),
                "due_date": instance.due_date.strftime("%A, %b %d, %Y") if instance.due_date else "N/A",
            }
        )


# ======================================================
# 2️⃣ MATERIAL NOTIFICATION
# ======================================================
@receiver(post_save, sender=Material)
def notify_material(sender, instance, created, **kwargs):
    if not created:
        return

    enrolled_user_ids = Enrollment.objects.filter(course=instance.course, is_active=True).values_list("user", flat=True)
    students = User.objects.filter(id__in=enrolled_user_ids)

    uploaded_on = localtime(instance.uploaded_at).strftime("%A, %b %d, %Y %H:%M") if instance.uploaded_at else "Not specified"
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

        send_student_email(
            to_email=student.email,
            subject=f"New Material Added: {instance.title}",
            template_name="material_notification",
            context={
                "student_name": student.get_full_name() or student.username,
                "course_name": str(instance.course),
                "material_title": instance.title,
                "material_description": instance.description or "No description provided.",
                "uploaded_on": uploaded_on,
                "instructor_name": instructor_name,
            }
        )


# ======================================================
# 3️⃣ LIVE SESSION NOTIFICATION
# ======================================================
@receiver(post_save, sender=LiveSession)
def notify_live_session(sender, instance, created, **kwargs):
    if not created:
        return

    assigned_students = instance.students.all()
    enrolled_ids = Enrollment.objects.filter(course=instance.course, is_active=True).values_list("user", flat=True)
    enrolled_students = User.objects.filter(id__in=enrolled_ids)

    students = set(list(assigned_students) + list(enrolled_students))
    join_link = getattr(instance, "join_link", "#")

    for student in students:
        if not getattr(student, "email", None):
            continue

        student_name = student.get_full_name() or str(student)

        # Dashboard notification
        Notification.objects.create(
            student=student,
            notif_type="live_session",
            title=f"New Live Session: {instance.title}",
            message=f"A new live session '{instance.title}' has been scheduled.\nClick here to join: {join_link}",
            obj_content_type=ContentType.objects.get_for_model(LiveSession),
            obj_id=instance.id,
        )

        send_student_email(
            to_email=student.email,
            subject=f"New Live Session Scheduled: {instance.title}",
            template_name="livesession_notification",
            context={
                "student_name": student_name,
                "course_name": str(instance.course),
                "session_title": instance.title,
                "session_description": instance.description or "No description provided.",
                "start_time": localtime(instance.start_time).strftime("%A, %b %d, %Y %H:%M") if instance.start_time else "",
                "end_time": localtime(instance.end_time).strftime("%A, %b %d, %Y %H:%M") if instance.end_time else "",
                "join_link": join_link,
                "instructor_name": str(getattr(instance, "instructor", "TBA")),
            }
        )


# ======================================================
# 4️⃣ TIMETABLE / SCHEDULE NOTIFICATION
# ======================================================
@receiver(post_save, sender=Timetable)
def notify_timetable(sender, instance, created, **kwargs):
    if not created:
        return

    user = instance.student
    if not user:
        return

    # Dashboard notification
    Notification.objects.create(
        student=user,
        notif_type="timetable",
        title="New Class Schedule",
        message=f"A new class timetable has been added for {instance.course}.",
        obj_content_type=ContentType.objects.get_for_model(Timetable),
        obj_id=instance.id,
    )

    # Brevo email
    send_student_email(
        to_email=user.email,
        subject="New Class Timetable Added",
        template_name="timetable_notification",
        context={
            "student_name": user.get_full_name() or user.username,
            "course_title": str(instance.course),
            "class_date": instance.date.strftime("%A, %b %d, %Y") if getattr(instance, "date", None) else "",
            "start_time": instance.start_time.strftime("%H:%M") if getattr(instance, "start_time", None) else "",
            "end_time": instance.end_time.strftime("%H:%M") if getattr(instance, "end_time", None) else "",
            "instructor_name": str(getattr(instance, "instructor", "")) or "TBA",
        }
    )


# ======================================================
# 5️⃣ ADMIN MESSAGE NOTIFICATION
# ======================================================
@receiver(post_save, sender=AdminMessage)
def notify_admin_message(sender, instance, created, **kwargs):
    if not created or instance.is_archived:
        return

    student = instance.student
    if not student or not getattr(student, "email", None):
        return

    # Dashboard notification
    Notification.objects.create(
        student=student,
        notif_type="admin_msg",
        title=f"Admin Message: {instance.title}",
        message=instance.message,
        obj_content_type=ContentType.objects.get_for_model(AdminMessage),
        obj_id=instance.id,
    )

    send_student_email(
        to_email=student.email,
        subject=f"Message from Admin: {instance.title}",
        template_name="admin_message_email",
        context={
            "title": instance.title,
            "content": instance.message,
            "student_name": student.get_full_name() or student.username,
        }
    )
    
#=========================================
#Schedule
#=========================================
@receiver(post_save, sender=GlobalTimetable)
def notify_globaltimetable(sender, instance, created, **kwargs):
    if not created:
        return  # Only notify on new timetable entries

    enrollments = Enrollment.objects.filter(course=instance.course).select_related("user")
    content_type = ContentType.objects.get_for_model(GlobalTimetable)

    for enr in enrollments:
        student = getattr(enr, "user", None)
        if not student:
            continue

        # --- Dashboard Notification ---
        Notification.objects.create(
            student=student,
            notif_type="schedule",
            title=f"New Class Scheduled: {instance.course.title}",
            message=(
                f"Class '{instance.course.title}' scheduled on {instance.date} "
                f"from {instance.start_time.strftime('%H:%M')} "
                f"to {instance.end_time.strftime('%H:%M')}. "
                f"Instructor: {instance.instructor or 'TBA'}."
            ),
            obj_content_type=content_type,
            obj_id=instance.id,
        )

        # --- Brevo Email ---
        if student.email:
            try:
                html_content = render_to_string(
                    "emails/globaltimetable_notification.html",  # your template
                    {
                        "student": student,   # matches {{ student.username }}
                        "schedule": instance  # matches {{ schedule.course.title }}, etc.
                    }
                )

                send_brevo_email(
                    to_email=student.email,
                    subject=f"New Class Scheduled: {instance.course.title}",
                    html_content=html_content,
                )

            except Exception as e:
                print(f"❌ Failed to send email to {student.email}: {e}")

# ======================================================
# 6️⃣ SECRET CODE GENERATION (plain text)
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

    plain_text_message = f"""
Hello {instance.full_name},

✅ Your enrollment has been confirmed.

Here is your secret login code: {code}

Use this code to log in via the secret login page.

Best regards,
STEM CodeMaster Team
"""

    # Send plain text email via Brevo
    try:
        send_brevo_email(
            to_email=instance.email,
            subject=f"Your STEM CodeMaster Secret Code{' (Auto)' if reason=='Bank transfer proof uploaded' else ''}",
            html_content=f"<pre>{plain_text_message}</pre>"
        )
        logger.info(f"[EMAIL SENT ✅] Secret code to {instance.email}")
    except Exception as e:
        logger.error(f"[EMAIL FAILED ❌] Secret code to {instance.email} | Error: {e}")

