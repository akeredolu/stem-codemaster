# services/utils.py
from xhtml2pdf import pisa
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import io

def generate_invoice_pdf(service_request):
    html = render_to_string(
        "services/invoice_template.html",
        {"service_request": service_request}
    )

    result = io.BytesIO()
    pdf = pisa.CreatePDF(
        io.BytesIO(html.encode("utf-8")),
        dest=result
    )

    if not pdf.err:
        return result.getvalue()
    return None


def send_invoice_email(service_request):
    pdf_bytes = generate_invoice_pdf(service_request)

    if pdf_bytes:
        email = EmailMessage(
            subject=f"Invoice for {service_request.service.name}",
            body="Thank you for requesting our services. Please find your invoice attached.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[service_request.email],
        )
        email.attach(
            f"Invoice_{service_request.id}.pdf",
            pdf_bytes,
            "application/pdf"
        )
        email.send(fail_silently=False)

