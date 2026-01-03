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
        to_email=recipient_email,
        subject=subject,
        template_name=None,  # No template, using raw HTML
        context=None,
        fallback_subject=subject,
        fallback_message=plain_message,
        fail_silently=True,
        html_message=html_message,
    )

