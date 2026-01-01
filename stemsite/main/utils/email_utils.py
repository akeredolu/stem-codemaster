# main/utils/email_utils.py

import logging
from django.conf import settings
from django.template import Template, Context
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from main.tasks import send_email_task
from main.models import (
    EmailTemplate,
    LiveSession,
    StudentCourse,
    Notification
)
from main.email_utils import send_email_async, send_plain_email_async

logger = logging.getLogger(__name__)

# -------------------------------
# Helper: Send templated email
# -------------------------------
def send_templated_email(student, template_name, context, fallback_subject, fallback_message):
    """
    Send an email using admin-defined EmailTemplate.
    If template not found, use fallback subject/message.
    """
    try:
        template = EmailTemplate.objects.get(name=template_name)
        subject = template.subject or fallback_subject
        body = Template(template.body).render(Context(context))
    except EmailTemplate.DoesNotExist:
        subject = fallback_subject
        body = fallback_message

    try:
        send_plain_email_async(
            subject=subject,
            message=body,
            recipients=[student.email],
            from_email=settings.DEFAULT_FROM_EMAIL,
            fail_silently=False,
        )
        logger.info(f"Email queued to {student.email} | Subject: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {student.email}: {e}")


# -------------------------------
# Enrollment / Payment Emails
# -------------------------------
def send_enrollment_payment_receipt(enrollment):
    """
    Send enrollment payment receipt.
    """
    amount = int(getattr(enrollment, "amount_paid", 10000))
    date = getattr(enrollment, "paid_at", None)
    date_str = date.strftime("%d %B, %Y at %I:%M %p") if date else ""

    fallback_subject = "Payment Receipt - STEM CodeMaster"
    fallback_message = f"""
Hello {enrollment.full_name},

We have received your enrollment fee payment of ₦{amount:,} on {date_str} via {enrollment.payment_method or 'Paystack'}.

Your enrollment is now active. 🎉

-- STEM CodeMaster Team
"""
    context = {
        "full_name": enrollment.full_name,
        "email": enrollment.email,
        "amount": f"₦{amount:,}",
        "date": date_str,
        "payment_method": enrollment.payment_method or "Paystack",
    }

    send_templated_email(
        enrollment,
        "Payment_Receipt",
        context,
        fallback_subject,
        fallback_message
    )


def send_payment_failure_notification(enrollment):
    fallback_subject = "Payment Verification Failed"
    fallback_message = f"""
Hello {enrollment.full_name},

Your payment could not be verified. Please try again or contact support.

-- STEM CodeMaster Team
"""
    send_templated_email(
        enrollment,
        "Payment_Failure_Notification",
        {"full_name": enrollment.full_name},
        fallback_subject,
        fallback_message
    )


def send_course_activation_notification(enrollment):
    fallback_subject = "Your Course Enrollment is Now Active!"
    fallback_message = f"""
Hello {enrollment.full_name},

Your course enrollment is now active! 🎉

You can log in to your dashboard to start learning.

-- STEM CodeMaster Team
"""
    send_templated_email(
        enrollment,
        "Course_Activation_Notification",
        {"full_name": enrollment.full_name},
        fallback_subject,
        fallback_message
    )


def send_password_reset_confirmation(enrollment):
    fallback_subject = "Password Reset Successful"
    fallback_message = f"""
Hello {enrollment.full_name},

Your password reset was successful. You can now log in with your new password.

-- STEM CodeMaster Team
"""
    send_templated_email(
        enrollment,
        "Password_Reset_Confirmation",
        {"full_name": enrollment.full_name},
        fallback_subject,
        fallback_message
    )


# -------------------------------
# Secret Code Email
# -------------------------------
def send_secret_code_email(enrollment, code):
    subject = "Your STEM CodeMaster Secret Code"
    message = f"""
Hello {enrollment.full_name},

✅ Your enrollment has been confirmed.

Here is your secret login code: {code}

Use this code to log in via the secret login page.

Best regards,  
STEM CodeMaster Team
"""
    send_plain_email_async(
        subject=subject,
        message=message,
        recipients=[enrollment.email],
        fail_silently=False
    )


# -------------------------------
# HTML Email Helper (async ready)
# -------------------------------
def send_html_email(subject, to_email, context, template):
    """
    Send HTML email synchronously.
    Recommended: wrap in Celery for async.
    """
    try:
        html_content = render_to_string(template, context)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        logger.info(f"HTML email sent to {to_email} | Subject: {subject}")
    except Exception as e:
        logger.error(f"Failed to send HTML email to {to_email}: {e}")


# -------------------------------
# Upcoming Live Session Reminders
# -------------------------------
def send_upcoming_live_session_reminders():
    """
    Sends 24-hour, 3-hour, and 1-hour reminders for upcoming live sessions.
    Also creates dashboard notifications for students.
    """
    now = timezone.now()

    def send_reminder(session, student, hours_left):
        context = {
            'name': student.get_full_name() or student.username,
            'course': session.course.title,
            'time': session.start_time.strftime('%A, %d %B %Y %I:%M %p'),
            'link': session.link,
        }

        if hours_left == 24:
            subject = f"⏰ Reminder: Your Live Session in 24 Hours – {session.course.title}"
            msg = f"Your live session '{session.title}' for {session.course.title} starts in 24 hours."
        elif hours_left == 3:
            subject = f"⚡ Reminder: Your Live Session in 3 Hours – {session.course.title}"
            msg = f"Your live session '{session.title}' for {session.course.title} starts in 3 hours."
        else:
            subject = f"🚨 Live Session Starting in 1 Hour – {session.course.title}"
            msg = f"Your live session '{session.title}' for {session.course.title} starts in 1 hour."

        # Send email
        send_html_email(subject, student.email, context, 'email/live_session_reminder.html')

        # Dashboard notification
        Notification.objects.create(
            student=student,
            notif_type='live',
            title=subject,
            message=msg,
            obj_content_type=ContentType.objects.get_for_model(LiveSession),
            obj_id=session.id
        )

    # 24-hour
    sessions_24hr = LiveSession.objects.filter(
        reminder_24hr_sent=False,
        start_time__gt=now,
        start_time__lte=now + timezone.timedelta(hours=24)
    )
    for session in sessions_24hr:
        students = StudentCourse.objects.filter(course=session.course)
        for sc in students:
            send_reminder(session, sc.student, 24)
        session.reminder_24hr_sent = True
        session.save()

    # 3-hour
    sessions_3hr = LiveSession.objects.filter(
        reminder_sent=False,
        start_time__gt=now,
        start_time__lte=now + timezone.timedelta(hours=3)
    )
    for session in sessions_3hr:
        students = StudentCourse.objects.filter(course=session.course)
        for sc in students:
            send_reminder(session, sc.student, 3)
        session.reminder_sent = True
        session.save()

    # 1-hour
    sessions_1hr = LiveSession.objects.filter(
        reminder_1hr_sent=False,
        start_time__gt=now,
        start_time__lte=now + timezone.timedelta(hours=1)
    )
    for session in sessions_1hr:
        students = StudentCourse.objects.filter(course=session.course)
        for sc in students:
            send_reminder(session, sc.student, 1)
        session.reminder_1hr_sent = True
        session.save()

# main/utils/email_utils.py
def send_payment_receipt(enrollment):
    """
    Send a payment receipt email to the student.
    """
    subject = f"Payment Receipt - {enrollment.course.title}"
    message = f"""
Hello {enrollment.full_name},

We have received your payment of ₦{enrollment.amount_paid} for the course '{enrollment.course.title}'.
Thank you for enrolling in STEM CodeMaster!

Best regards,
STEM CodeMaster Team
"""
    # Send asynchronously via Celery
    send_email_task.delay(
        to_email=enrollment.email,
        subject=subject,
        message=message
    )
