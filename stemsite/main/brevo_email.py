import requests
from django.conf import settings


BREVO_SEND_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"


def send_brevo_email(to_email, subject, html_content):
    """
    Send email using Brevo HTTP API (Render free-tier safe)
    """

    if not settings.BREVO_API_KEY:
        raise ValueError("BREVO_API_KEY is not set")

    headers = {
        "api-key": settings.BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "sender": {
            "name": settings.BREVO_SENDER_NAME,
            "email": settings.BREVO_SENDER_EMAIL,
        },
        "to": [
            {
                "email": to_email,
            }
        ],
        "subject": subject,
        "htmlContent": html_content,
    }

    response = requests.post(
        BREVO_SEND_EMAIL_URL,
        headers=headers,
        json=payload,
        timeout=10,
    )

    if response.status_code not in (200, 201):
        raise Exception(
            f"Brevo email failed "
            f"[{response.status_code}]: {response.text}"
        )

    return True

