#from django.core.mail import send_mail
from main.utils.email_service import send_email_async
from django.conf import settings

def send_activation_email(enrollment):
    if enrollment.is_activation_email_sent:
        return False  # already sent, skip
    
    subject = "Welcome to STEM CodeMaster – Activate Your Account"
    message = f"Hello {enrollment.user.first_name},\n\nYour account has been activated successfully."
    
    send_email_async(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [enrollment.email],
        fail_silently=True,
    )
    
    enrollment.is_activation_email_sent = True
    enrollment.save(update_fields=["is_activation_email_sent"])
    return True

