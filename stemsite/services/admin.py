# services/admin.py
from django.conf import settings
from django.core.mail import send_mail
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect
from django.utils.html import format_html
from django.contrib import admin

from .models import (
    Service,
    Testimonial,
    ServiceRequest,
    Payment,
    BankDetail,
)
from .utils import send_invoice_email


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("client_name", "client_title", "is_active")
    list_filter = ("is_active",)
    search_fields = ("client_name", "client_title", "feedback")


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "service",
        "name",
        "email",
        "status",
        "amount_due",
        "confirm_bank_payment",
        "payment_link",
    )
    list_filter = ("status",)
    search_fields = ("name", "email", "service__name")
    readonly_fields = ("created_at",)

    # 🔹 Custom admin URLs
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "confirm-bank/<int:pk>/",
                self.admin_site.admin_view(self.confirm_bank),
                name="services_confirm_bank",
            ),
        ]
        return custom_urls + urls

    # 🔹 Confirm bank payment
    def confirm_bank(self, request, pk):
        service_request = get_object_or_404(ServiceRequest, pk=pk)

        payment = service_request.payments.filter(
            method="bank",
            is_confirmed=False
        ).first()

        if payment:
            payment.is_confirmed = True
            payment.save()

            service_request.status = "paid"
            service_request.save()

            send_invoice_email(service_request)
            self.message_user(
                request,
                "Bank payment confirmed and invoice sent.",
            )

        return redirect("admin:services_servicerequest_changelist")

    # 🔹 Confirm button in list
    def confirm_bank_payment(self, obj):
        payment = obj.payments.filter(
            method="bank",
            is_confirmed=False
        ).first()

        if payment and obj.status != "paid":
            url = reverse(
                "admin:services_confirm_bank",
                args=[obj.id],
            )
            return format_html(
                '<a class="button" href="{}">Confirm</a>',
                url,
            )
        return "-"

    confirm_bank_payment.short_description = "Confirm Bank Payment"

    # 🔹 Payment link column
    def payment_link(self, obj):
        if obj.status == "approved":
            url = reverse(
                "payment_page",
                args=[obj.id],
            )
            return format_html(
                '<a href="{}" target="_blank">Payment Page</a>',
                url,
            )
        return "-"

    payment_link.short_description = "Payment Link"

    # 🔹 Send payment link email when approved
    def save_model(self, request, obj, form, change):
        status_changed = False

        if change:
            old = ServiceRequest.objects.get(pk=obj.pk)
            status_changed = (
                old.status != "approved"
                and obj.status == "approved"
            )
        else:
            status_changed = obj.status == "approved"

        super().save_model(request, obj, form, change)

        if status_changed:
            payment_url = request.build_absolute_uri(
                reverse("payment_page", args=[obj.id])
            )

            send_mail(
                subject="Payment Link – STEM CodeMaster",
                message=(
                    f"Hello {obj.name},\n\n"
                    f"Your request for {obj.service.name} has been approved.\n"
                    f"Amount Due: ₦{obj.amount_due}\n\n"
                    f"Please make payment using the link below:\n"
                    f"{payment_url}\n\n"
                    "Thank you."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[obj.email],
                fail_silently=False,
            )



@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "service_request",
        "method",
        "is_confirmed",
        "created_at",
    )
    list_filter = ("method", "is_confirmed")
    readonly_fields = ("created_at",)


@admin.register(BankDetail)
class BankDetailAdmin(admin.ModelAdmin):
    list_display = ("bank_name", "account_name", "account_number", "is_active")
    list_filter = ("is_active",)

