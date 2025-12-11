# main/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from django.contrib.contenttypes.models import ContentType

from .models import Enrollment, CoursePayment  # make sure CoursePayment is imported


from .models import (
    Assignment,
    Material,
    LiveSession,
    Timetable,
    AdminMessage,
    Notification,
    Enrollment,
)

logger = logging.getLogger(__name__)


# -------------------------------
# HELPER — Send HTML Email
# -------------------------------
def send_student_email(to_email, subject, template_name, context):
    try:
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Email sending failed to {to_email}: {e}")


# ======================================================
# 1️⃣ ASSIGNMENT NOTIFICATION + EMAIL
# ======================================================
@receiver(post_save, sender=Assignment)
def notify_assignment(sender, instance, created, **kwargs):
    if created:
        enrollments = Enrollment.objects.filter(course=instance.course)
        for enroll in enrollments:
            Notification.objects.create(
                student=enroll.user,
                notif_type="assignment",
                title=f"New Assignment: {instance.title}",
                message=f"A new assignment '{instance.title}' was added.",
                obj_content_type=ContentType.objects.get_for_model(Assignment),
                obj_id=instance.id,
            )

            send_student_email(
                to_email=enroll.user.email,
                subject=f"New Assignment: {instance.title}",
                template_name="emails/assignment_notification.html",
                context={"student": enroll.user, "assignment": instance},
            )


# ======================================================
# 2️⃣ MATERIAL NOTIFICATION + EMAIL
# ======================================================
@receiver(post_save, sender=Material)
def notify_material(sender, instance, created, **kwargs):
    if created:
        enrollments = Enrollment.objects.filter(course=instance.course)
        for enroll in enrollments:
            Notification.objects.create(
                student=enroll.user,
                notif_type="material",
                title=f"New Material: {instance.title}",
                message=f"New learning material '{instance.title}' is available.",
                obj_content_type=ContentType.objects.get_for_model(Material),
                obj_id=instance.id,
            )

            send_student_email(
                to_email=enroll.user.email,
                subject=f"New Material: {instance.title}",
                template_name="emails/material_notification.html",
                context={"student": enroll.user, "material": instance},
            )


# ======================================================
# 3️⃣ LIVE SESSION NOTIFICATION + EMAIL
# ======================================================
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=LiveSession)
def notify_live_session(sender, instance, created, **kwargs):
    if created:
        try:
            # Students explicitly assigned to this live session
            assigned_students = instance.students.all()

            # Students enrolled in the course
            course_enrollments = Enrollment.objects.filter(course=instance.course)
            enrolled_students = [enr.user for enr in course_enrollments]

            # Combine and remove duplicates
            all_students = list(set(list(assigned_students) + enrolled_students))

            for student in all_students:
                # Log notification
                print(f"Notify {student.username} about live session '{instance.title}'")

                # Send email if student has email
                if student.email:
                    subject = f"New Live Session: {instance.title}"
                    message = f"""
Hello {getattr(student, 'full_name', student.username)},

A new live session has been scheduled:

Title: {instance.title}
Course: {instance.course.title}
Start: {instance.start_time.strftime('%d %b %Y %H:%M')}
End: {instance.end_time.strftime('%d %b %Y %H:%M') if instance.end_time else 'N/A'}
Link: {instance.link}

Please join on time.
"""
                    send_mail(
                        subject,
                        message,
                        'admin@yourdomain.com',
                        [student.email],
                        fail_silently=True,  # prevents breaking admin
                    )
        except Exception as e:
            print(f"Error in live session notification: {e}")

# ======================================================
# 4️⃣ CLASS TIMETABLE / SCHEDULE NOTIFICATION + EMAIL
# ======================================================
@receiver(post_save, sender=Timetable)
def notify_timetable(sender, instance, created, **kwargs):
    if created:
        enrollments = Enrollment.objects.filter(course=instance.course)

        for enroll in enrollments:
            Notification.objects.create(
                student=enroll.user,
                notif_type="schedule",
                title="New Class Schedule",
                message=f"A new schedule has been added for {instance.course}.",
                obj_content_type=ContentType.objects.get_for_model(Timetable),
                obj_id=instance.id,
            )

            send_student_email(
                to_email=enroll.user.email,
                subject="New Class Schedule Added",
                template_name="emails/timetable_notification.html",
                context={"student": enroll.user, "timetable": instance},
            )


# ======================================================
# 5️⃣ ADMIN MESSAGE NOTIFICATION + EMAIL
# ======================================================
@receiver(post_save, sender=AdminMessage)
def notify_admin_message(sender, instance, created, **kwargs):
    if created and not instance.is_archived:
        # Dashboard notification
        Notification.objects.create(
            student=instance.student,
            notif_type="admin_msg",
            title=f"Admin Message: {instance.title}",
            message=instance.message,
            obj_content_type=ContentType.objects.get_for_model(AdminMessage),
            obj_id=instance.id,
        )

        # Email
        send_student_email(
            to_email=instance.student.email,
            subject=f"Message from Admin: {instance.title}",
            template_name="emails/admin_message_email.html",
            context={
                "title": instance.title,
                "content": instance.message,
                "student_name": instance.student.get_full_name() or instance.student.username   # used for personalized greeting
            },
        )


# ======================================================
# SECRET CODE GENERATION (ADMIN CONFIRMED OR BANK PROOF)
# ======================================================
@receiver(post_save, sender=Enrollment)
def generate_secret_code(sender, instance, created, **kwargs):
    """
    Unified secret code generator:
    - Admin confirmed payment (is_enrollment_paid=True)
    - OR student uploaded bank transfer proof (payment_method="bank" + proof_of_payment)
    
    Ensures:
    - Secret code generated only once
    - Admin manual flow still works
    - Auto-send flow allows student to continue immediately
    """
    # Skip new enrollment creation
    if created:
        return

    # Skip if secret code already exists
    if instance.secret_code:
        return

    # Determine if we should generate the secret code
    should_generate = False
    reason = ""

    # Admin-confirmed payment
    if instance.is_enrollment_paid:
        should_generate = True
        reason = "Admin confirmed payment"

    # Bank transfer proof uploaded
    elif instance.payment_method == "bank" and instance.proof_of_payment:
        should_generate = True
        reason = "Bank transfer proof uploaded"

    if not should_generate:
        return

    # Generate and persist secret code
    try:
        code = instance.generate_and_set_secret_code()
    except Exception as e:
        print(f"⚠️ Failed to generate secret code for enrollment {instance.id}: {e}")
        return

    # Send email
    try:
        subject_suffix = "(Auto)" if reason == "Bank transfer proof uploaded" else ""
        send_mail(
            subject=f"Your STEM CodeMaster Secret Code {subject_suffix}",
            message=(
                f"Hello {instance.full_name},\n\n"
                f"Your secret login code is: {code}\n\n"
                "Use it to log in via the secret login page."
                + ("\n\nYou can continue immediately without waiting for admin confirmation." if reason == "Bank transfer proof uploaded" else "")
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
            fail_silently=False,
        )
        print(f"✅ Secret code sent for enrollment {instance.id} ({reason})")
    except Exception as e:
        print(f"⚠️ Failed to send secret code email for enrollment {instance.id}: {e}")
