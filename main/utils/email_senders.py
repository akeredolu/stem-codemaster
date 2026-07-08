from django.conf import settings

def send_activation_email(enrollment):
    if enrollment.is_activation_email_sent:
        return False  # Already sent, skip

    subject = "Welcome to STEM CodeMaster – Activate Your Account"
    message = (
        f"Hello {enrollment.user.first_name},\n\n"
        "Your account has been activated successfully. "
        "You can now log in and start learning!"
    )

    send_plain_email_async(
        subject=subject,
        message=message,
        recipients=[enrollment.email],
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=True,
    )

    enrollment.is_activation_email_sent = True
    enrollment.save(update_fields=["is_activation_email_sent"])
    return True

