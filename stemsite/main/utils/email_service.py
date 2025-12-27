import threading
import logging
from django.core.mail import EmailMessage
from django.conf import settings

logger = logging.getLogger(__name__)

def send_email_async(
    subject: str,
    message: str = "",
    recipients: list = None,
    html_message: str = None,
    from_email: str = None,
    fail_silently: bool = True,  # ✅ True for production
):
    """
    Async email sender for production: works safely on Render or any server.
    """

    if not recipients:
        logger.warning("No recipients specified for email. Aborting send.")
        return

    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL

    def _send():
        try:
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=recipients,
            )
            if html_message:
                email.content_subtype = "html"
                email.body = html_message

            email.send(fail_silently=fail_silently)
            logger.info(f"Email sent successfully to: {recipients}")

        except Exception as e:
            # Logs the error in server logs, does NOT break the app
            logger.error(f"Email sending failed: {e}")

    threading.Thread(target=_send, daemon=True).start()

