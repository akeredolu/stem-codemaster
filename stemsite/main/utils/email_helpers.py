#from django.core.mail import send_mail
from main.utils.email_service import send_email_async
from django.conf import settings
from django.utils.html import strip_tags

def send_broadcast_email(recipient_email, subject, context):
    """
    Test broadcast email: simple HTML email to check delivery.
    """
    # Minimal HTML content
    html_message = f"""
    <html>
        <body>
            <h2>{context.get('title', '')}</h2>
            <p>{context.get('content', '')}</p>
        </body>
    </html>
    """
    plain_message = strip_tags(html_message)

    send_email_async(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        html_message=html_message,
        fail_silently=True,
    )

