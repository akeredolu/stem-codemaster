# main/email_utils.py
from main.tasks import send_email_task, send_templated_email_task

def send_email_async(to_email, subject, template_name, context):
    """
    Send templated HTML emails asynchronously via Celery
    """
    send_templated_email_task.delay(
        to_email=to_email,
        subject=subject,
        template_name=template_name,
        context=context
    )

def send_plain_email_async(subject, message, recipients, fail_silently=True):
    """
    Send plain text emails asynchronously via Celery
    """
    send_email_task.delay(subject, message, recipients, fail_silently)

