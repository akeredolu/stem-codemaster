# services/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
import requests

from .models import Service, Testimonial, ServiceRequest, BankDetail, Payment
from .forms import ServiceRequestForm, PaymentForm
from main.brevo_email import send_brevo_email  # ✅ Correct import from main app


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

            # Notify admin about the new request via Brevo
            subject = f"New Service Request: {service_request.service.name}"
            plain_text = (
                f"Name: {service_request.name}\n"
                f"Email: {service_request.email}\n"
                f"Phone: {service_request.phone}\n"
                f"Details: {service_request.details}"
            )

            send_brevo_email(
                to_email=settings.ADMIN_EMAIL,
                subject=subject,
                plain_text=plain_text
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
        "amount": int(service_request.amount_due * 100),
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

        # Send invoice after payment via Brevo
        subject = f"Invoice for Service: {service_request.service.name}"
        plain_text = (
            f"Hello {service_request.name},\n\n"
            f"Your payment of ₦{service_request.amount_due} for the service "
            f"'{service_request.service.name}' has been confirmed.\n\n"
            "Thank you for choosing our services!"
        )

        send_brevo_email(
            to_email=service_request.email,
            subject=subject,
            plain_text=plain_text
        )

        return redirect("services_thank_you")

    return redirect("our_services")


def payment_page(request, service_request_id):
    """Separate payment page for approved service requests."""
    service_request = get_object_or_404(ServiceRequest, id=service_request_id, status="approved")
    bank_details = BankDetail.objects.filter(is_active=True)

    if request.method == "POST":
        form = PaymentForm(request.POST, request.FILES)
        method = request.POST.get("method")

        if method == "bank":
            if form.is_valid():
                payment = form.save(commit=False)
                payment.service_request = service_request
                payment.method = "bank"
                payment.save()

                # Send invoice / pending confirmation email via Brevo
                subject = f"Invoice Pending for Service: {service_request.service.name}"
                plain_text = (
                    f"Hello {service_request.name},\n\n"
                    f"We have received your bank payment submission for '{service_request.service.name}'. "
                    "It is pending verification. We will notify you once confirmed.\n\n"
                    "Thank you!"
                )

                send_brevo_email(
                    to_email=service_request.email,
                    subject=subject,
                    plain_text=plain_text
                )

                return render(
                    request,
                    "services/payment_pending.html",
                    {"service_request": service_request},
                )

        elif method == "paystack":
            return redirect("pay_service", service_request_id=service_request.id)

    else:
        form = PaymentForm()

    return render(
        request,
        "services/payment_page.html",
        {
            "service_request": service_request,
            "bank_details": bank_details,
            "payment_form": form,
        },
    )

