from django.template.loader import render_to_string
from django.utils import timezone
from main.models import LiveSession, StudentCourse

def send_upcoming_live_session_reminders():
    now = timezone.now()

    def send_reminder(sessions, reminder_type, hours):
        for session in sessions:
            students = StudentCourse.objects.filter(course=session.course)
            for sc in students:
                context = {
                    'name': sc.student.get_full_name() or sc.student.username,
                    'course': session.course.title,
                    'time': session.start_time.strftime('%A, %d %B %Y %I:%M %p'),
                    'link': session.link,
                }
                subject = f"{reminder_type} Reminder – {session.course.title}"
                html_message = render_to_string('emails/live_session_reminder.html', context)
                plain_message = f"Reminder: Your live session for {session.course.title} is coming up at {context['time']}."

                # ✅ Send asynchronously
                send_email_async(
                    subject=subject,
                    message=plain_message,
                    recipients=[sc.student.email],
                    html_message=html_message,
                    fail_silently=True,
                )

            # Mark session reminder sent
            if hours == 24:
                session.reminder_24hr_sent = True
            elif hours == 1:
                session.reminder_1hr_sent = True
            session.save()

    # 24-hour reminders
    sessions_24hr = LiveSession.objects.filter(
        reminder_24hr_sent=False,
        start_time__gt=now,
        start_time__lte=now + timezone.timedelta(hours=24)
    )
    send_reminder(sessions_24hr, "⏰ 24-Hour", 24)

    # 1-hour reminders
    sessions_1hr = LiveSession.objects.filter(
        reminder_1hr_sent=False,
        start_time__gt=now,
        start_time__lte=now + timezone.timedelta(hours=1)
    )
    send_reminder(sessions_1hr, "🚨 1-Hour", 1)
