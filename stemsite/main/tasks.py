from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

@shared_task
def send_templated_email_task(to_email, subject, template_name, context):
    """
    Sends an HTML email asynchronously using Celery.
    """
    # Render HTML content
    html_content = render_to_string(template_name, context)

    # Create email
    email = EmailMultiAlternatives(
        subject=subject,
        body=html_content,  # Fallback plain text
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


@shared_task
def send_email_task(subject, message, recipients, fail_silently=True):
    """
    Sends a plain text email asynchronously using Celery.
    """
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        fail_silently=fail_silently
    )

