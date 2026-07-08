# services/admin.py
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.utils.html import format_html
from django.contrib import admin
from django.urls import reverse, NoReverseMatch

from .models import (
    Service,
    Testimonial,
    ServiceRequest,
    Payment,
    BankDetail,
)
from main.brevo_email import send_brevo_email


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
    
    actions = ["mark_as_paid_and_send_invoice"]

    @admin.action(description="Confirm selected Bank Payments & Send Invoices")
    def mark_as_paid_and_send_invoice(self, request, queryset):
        success_count = 0
        for service_request in queryset:
            pending_payments = service_request.payments.filter(is_confirmed=False)
            for payment in pending_payments:
                payment.is_confirmed = True
                payment.save()  # ✅ This triggers the new automatic save logic!
                success_count += 1
        
        if success_count > 0:
            self.message_user(request, f"Successfully processed actions for payments.")

    def confirm_bank_payment(self, obj):
        if obj.status != "paid":
            return format_html('<span style="color: #ffc107; font-weight: bold;">⏳ Awaiting Action</span>')
        return format_html('<span style="color: #198754; font-weight: bold;">✓ Settled & Sent</span>')

    confirm_bank_payment.short_description = "Bank Payment Status"

    def payment_link(self, obj):
        if obj.status == "approved":
            try:
                url = reverse("payment_page", args=[obj.id])
                return format_html('<a href="{}" target="_blank">Payment Page</a>', url)
            except NoReverseMatch:
                return "-"
        return "-"

    payment_link.short_description = "Payment Link"

    def save_model(self, request, obj, form, change):
        status_changed = False
        if change:
            old = ServiceRequest.objects.get(pk=obj.pk)
            status_changed = (old.status != "approved" and obj.status == "approved")
        else:
            status_changed = obj.status == "approved"

        super().save_model(request, obj, form, change)

        if status_changed:
            from decimal import Decimal

            # 1. Force the database value to a Decimal safely
            amount = obj.amount_due if obj.amount_due is not None else Decimal('0.00')
            
            # 2. Strict Decimal-to-Decimal multiplication
            deposit_decimal = amount * Decimal('0.10')
            balance_decimal = amount * Decimal('0.90')

            # 3. Convert to float *strictly for the comma string formatting* display
            amount_display = float(amount)
            deposit_display = float(deposit_decimal)
            balance_display = float(balance_decimal)

            payment_url = request.build_absolute_uri(reverse("payment_page", args=[obj.id]))
            subject = "Payment Link – STEM CodeMaster"
            
            html_content = (
                f"<p>Hello {obj.name},</p>"
                f"<p>Your request for '<strong>{obj.service.name}</strong>' has been approved.</p>"
                f"<p><strong>Payment Breakdown:</strong><br>"
                f"- Total Service Cost: ₦{amount_display:,}<br>"
                f"- Deposit Due Now (10%): ₦{deposit_display:,}<br>"
                f"- Remaining Balance (90%): ₦{balance_display:,}</p>"
                f"<p>Please click the secure link below to pay your 10% deposit to secure your booking:<br>"
                f"<a href='{payment_url}' target='_blank'>{payment_url}</a></p>"
                f"<p><em>Note: The remaining balance of ₦{balance_display:,} will be due upon completion of the service.</em></p>"
                f"<p>Thank you.</p>"
            )
            send_brevo_email(to_email=obj.email, subject=subject, html_content=html_content)

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
    
    # ✅ Fixes direct manual edits in the individual Payment change page
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)


@admin.register(BankDetail)
class BankDetailAdmin(admin.ModelAdmin):
    list_display = ("bank_name", "account_name", "account_number", "is_active")
    list_filter = ("is_active",)
