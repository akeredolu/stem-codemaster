# services/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
#from django.core.mail import send_mail
from main.utils.email_service import send_email_async
import requests

from .models import Service, Testimonial, ServiceRequest, BankDetail, Payment
from .forms import ServiceRequestForm, PaymentForm
from .utils import send_invoice_email


def our_services(request):
    """Display services, testimonials, and handle service request submissions without payment."""
    services = Service.objects.filter(is_active=True)
    testimonials = Testimonial.objects.filter(is_active=True)

    if request.method == "POST":
        form = ServiceRequestForm(request.POST)
        if form.is_valid():
            service_request = form.save(commit=False)
            service_request.status = "new"  # New request
            service_request.save()

            # Notify admin about the new request
            send_email_async(
                subject=f"New Service Request: {service_request.service.name}",
                message=(
                    f"Name: {service_request.name}\n"
                    f"Email: {service_request.email}\n"
                    f"Phone: {service_request.phone}\n"
                    f"Details: {service_request.details}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )

            # Redirect to a simple thank-you page
            return redirect("services_thank_you")

    else:
        form = ServiceRequestForm()

    return render(
        request,
        "services/our_services.html",
        {
            "services": services,
            "testimonials": testimonials,
            "form": form,
        },
    )



def pay_service(request, service_request_id):
    """Redirect user to Paystack payment page."""
    service_request = get_object_or_404(ServiceRequest, id=service_request_id)

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "email": service_request.email,
        "amount": int(service_request.amount_due * 100),  # Use amount_due
        "callback_url": request.build_absolute_uri(
            f"/services/paystack/callback/{service_request.id}/"
        ),
        "metadata": {"service_request_id": service_request.id},
    }

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=data,
        headers=headers,
    )

    res = response.json()
    if res.get("status"):
        return redirect(res["data"]["authorization_url"])

    # If Paystack fails, redirect back to services
    return redirect("our_services")


def paystack_callback(request, service_request_id):
    """Handle Paystack callback verification."""
    service_request = get_object_or_404(ServiceRequest, id=service_request_id)
    reference = request.GET.get("reference")

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

    res = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers=headers,
    ).json()

    if res.get("status") and res["data"]["status"] == "success":
        # Mark payment as completed
        Payment.objects.create(
            service_request=service_request,
            method="paystack",
            reference=reference,
            is_confirmed=True,
        )
        service_request.status = "paid"
        service_request.save()

        # Send invoice after payment
        send_invoice_email(service_request)

        return redirect("services_thank_you")

    # Payment failed → keep status unchanged
    return redirect("our_services")


def payment_page(request, service_request_id):
    """Separate payment page for approved service requests."""
    service_request = get_object_or_404(ServiceRequest, id=service_request_id, status="approved")
    bank_details = BankDetail.objects.filter(is_active=True)

    if request.method == "POST":
        form = PaymentForm(request.POST, request.FILES)
        method = request.POST.get("method")  # Determine which payment method was submitted

        if method == "bank":
            if form.is_valid():
                payment = form.save(commit=False)
                payment.service_request = service_request
                payment.method = "bank"
                payment.save()

                # Optionally, send invoice or pending confirmation email
                send_invoice_email(service_request)
                return render(
                    request,
                    "services/payment_pending.html",
                    {"service_request": service_request},
                )

        elif method == "paystack":
            # Redirect to Paystack payment
            return redirect("pay_service", service_request_id=service_request.id)

    else:
        form = PaymentForm()

    return render(
        request,
        "services/payment_page.html",
        {
            "service_request": service_request,
            "bank_details": bank_details,
            "payment_form": form,  # pass as payment_form to match template
        },
    )