#------------General Helper Function-----------
# main/utils/email_utils.py

from django.core.mail import send_mail
from django.conf import settings
from django.template import Template, Context
from main.models import EmailTemplate

from django.core.mail import EmailMessage

from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from main.models import LiveSession, StudentCourse, Notification


def send_templated_email(student, template_name, context, fallback_subject, fallback_message):
    """
    Try sending using EmailTemplate in admin, otherwise send fallback.
    """
    try:
        template = EmailTemplate.objects.get(name=template_name)
        subject = template.subject or fallback_subject
        body = Template(template.body).render(Context(context))
    except EmailTemplate.DoesNotExist:
        subject = fallback_subject
        body = fallback_message

    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [student.email],
        fail_silently=False,
    )


#----------All EmailTemplate----------
# ---------- Unified Course Payment Receipt ----------
def send_payment_receipt(payment):
    enrollment = payment.enrollment

    context = {
        "full_name": enrollment.full_name,
        "email": enrollment.email,
        "course": payment.course.title,
        "amount": f"₦{payment.amount_paid:,.2f}",
        "date": payment.created_at.strftime("%d %B, %Y at %I:%M %p"),
        "payment_method": payment.get_payment_method_display(),
        "reference": payment.reference,
    }

    # Check payment method
    if payment.payment_method.lower() == "bank":
        template_name = "Course_Payment_BankReceipt"
        fallback_subject = f"Bank Transfer Payment Pending - {payment.course.title}"
        fallback_message = f"""
Hello {enrollment.full_name},

We have received your payment request of {context['amount']} on {context['date']} 
via Bank Transfer for the course "{context['course']}".

Reference: {context['reference']}

✅ Note: Your payment will be verified by our admin team shortly.
Once confirmed, your course will be activated and you will receive another email.

Thank you for your patience.

-- STEM CodeMaster Team
"""
    else:
        template_name = "Course_Payment_Receipt"
        fallback_subject = f"Payment Receipt - {payment.course.title}"
        fallback_message = f"""
Hello {enrollment.full_name},

We have received your payment of {context['amount']} on {context['date']} 
via {context['payment_method']} for the course "{context['course']}".

Reference: {context['reference']}

Your course is now active. 🎉

You can log in to your dashboard to start learning.

-- STEM CodeMaster Team
"""

    # Send email using selected template
    send_templated_email(
        enrollment,
        template_name,
        context,
        fallback_subject,
        fallback_message
    )


def send_payment_failure_notification(enrollment):
    context = {
        "full_name": enrollment.full_name,
    }

    fallback_subject = "Payment Verification Failed"
    fallback_message = f"""
Hello {enrollment.full_name},

Your payment could not be verified. Please try again or contact support.

-- STEM CodeMaster Team
"""

    send_templated_email(
        enrollment,
        "Payment_Failure_Notification",
        context,
        fallback_subject,
        fallback_message
    )


def send_course_activation_notification(enrollment):
    context = {
        "full_name": enrollment.full_name,
    }

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
        context,
        fallback_subject,
        fallback_message
    )


def send_password_reset_confirmation(enrollment):
    context = {
        "full_name": enrollment.full_name,
    }

    fallback_subject = "Password Reset Successful"
    fallback_message = f"""
Hello {enrollment.full_name},

Your password reset was successful. You can now log in with your new password.

-- STEM CodeMaster Team
"""

    send_templated_email(
        enrollment,
        "Password_Reset_Confirmation",
        context,
        fallback_subject,
        fallback_message
    )

#---------------Added----------------
from main.utils.settings_utils import get_setting

def send_payment_receipt(enrollment):
    amount = int(get_setting("ENROLLMENT_FEE", 10000))  # fallback if not set in admin

    context = {
        "full_name": enrollment.full_name,
        "email": enrollment.email,
        "amount": f"₦{amount:,.0f}",  # format as ₦10,000
        "date": enrollment.paid_at.strftime("%d %B, %Y at %I:%M %p") if enrollment.paid_at else "",
        "payment_method": enrollment.payment_method or "Paystack",
    }

    fallback_subject = "Payment Receipt - STEM CodeMaster"
    fallback_message = f"""
Hello {enrollment.full_name},

We have received your enrollment fee payment of {context['amount']} on {context['date']} via {context['payment_method']}.

Your enrollment is now active. 🎉

-- STEM CodeMaster Team
"""

    send_templated_email(
        enrollment,
        "Payment_Receipt",
        context,
        fallback_subject,
        fallback_message
    )


#------------Live Session Reminder-------------
def send_html_email(subject, to_email, context, template):
    html_content = render_to_string(template, context)
    text_content = f"{context['course']} session is coming up."

    email = EmailMultiAlternatives(subject, text_content, 'noreply@stemcodemaster.com', [to_email])
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_upcoming_live_session_reminders():
    """
    Sends 24-hour, 3-hour, and 1-hour reminders for upcoming live sessions.
    Also creates in-app dashboard notifications for students.
    """
    now = timezone.now()

    # Helper function to send both email + dashboard notification
    def send_reminder(session, student, hours_left):
        context = {
            'name': student.get_full_name() or student.username,
            'course': session.course.title,
            'time': session.start_time.strftime('%A, %d %B %Y %I:%M %p'),
            'link': session.link,
        }

        # Subject varies by time
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

        # Create dashboard notification
        Notification.objects.create(
            student=student,
            notif_type='live',
            title=subject,
            message=msg,
            obj_content_type=ContentType.objects.get_for_model(LiveSession),
            obj_id=session.id
        )

    # --- 24-HOUR REMINDERS ---
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

    # --- 3-HOUR REMINDERS ---
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

    # --- 1-HOUR REMINDERS ---
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