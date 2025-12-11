from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from main.models import LiveSession, StudentCourse


from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def send_html_email(subject, to_email, context, template):
    html_content = render_to_string(template, context)
    # safer access
    course_title = context.get('course', 'Your course')
    text_content = f"{course_title} session is coming up."

    email = EmailMultiAlternatives(subject, text_content, 'noreply@stemcodemaster.com', [to_email])
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_upcoming_live_session_reminders():
    now = timezone.now()

    # 1. 24-hour reminder
    sessions_24hr = LiveSession.objects.filter(
        reminder_24hr_sent=False,
        start_time__gt=now,
        start_time__lte=now + timezone.timedelta(hours=24)
    )

    for session in sessions_24hr:
        students = StudentCourse.objects.filter(course=session.course)
        for sc in students:
            context = {
                'name': sc.student.get_full_name() or sc.student.username,
                'course': session.course.title,
                'time': session.start_time.strftime('%A, %d %B %Y %I:%M %p'),
                'link': session.link,
            }
            subject = f"⏰ Reminder: Your Live Session in 24 Hours – {session.course.title}"
            send_html_email(subject, sc.student.email, context, 'email/live_session_reminder.html')
        session.reminder_24hr_sent = True
        session.save()

    # 2. 1-hour reminder
    sessions_1hr = LiveSession.objects.filter(
        reminder_1hr_sent=False,
        start_time__gt=now,
        start_time__lte=now + timezone.timedelta(hours=1)
    )

    for session in sessions_1hr:
        students = StudentCourse.objects.filter(course=session.course)
        for sc in students:
            context = {
                'name': sc.student.get_full_name() or sc.student.username,
                'course': session.course.title,
                'time': session.start_time.strftime('%A, %d %B %Y %I:%M %p'),
                'link': session.link,
            }
            subject = f"🚨 Live Session Starting in 1 Hour – {session.course.title}"
            send_html_email(subject, sc.student.email, context, 'email/live_session_reminder.html')
        session.reminder_1hr_sent = True
        session.save()
