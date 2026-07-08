# services/models.py
from django.db import models
from cloudinary_storage.storage import RawMediaCloudinaryStorage


class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.ImageField(upload_to="services/icons/", blank=True, null=True)
    
    # ✅ FIX 1: Consolidated into one single declaration with correct Cloudinary storage setup
    brochure = models.FileField(
        upload_to="services/brochures/",
        storage=RawMediaCloudinaryStorage(),
        blank=True,
        null=True
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def brochure_download_url(self):
        if self.brochure:
            url = self.brochure.url
            if "/raw/upload/" in url:
                return url.replace("/raw/upload/", "/raw/upload/fl_attachment/")
            return url
        return ""


class Testimonial(models.Model):
    client_name = models.CharField(max_length=100)
    client_title = models.CharField(max_length=100, blank=True)
    feedback = models.TextField()
    photo = models.ImageField(upload_to="testimonials/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.client_name


class ServiceRequest(models.Model):
    STATUS_CHOICES = (
        ("new", "New Request"),
        ("approved", "Approved – Awaiting Payment"),
        ("paid", "Paid"),
    )

    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    details = models.TextField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} – {self.service.name}"


class Payment(models.Model):
    PAYMENT_METHODS = (
        ("paystack", "Paystack"),
        ("bank", "Bank Transfer"),
    )

    service_request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    reference = models.CharField(max_length=100, blank=True)
    proof = models.FileField(upload_to="payment_proofs/", blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment #{self.id} ({self.get_method_display()}) for Request #{self.service_request.id}"

    # ✅ AUTOMATIC TRIGGER ON SAVE
    def save(self, *args, **kwargs):
        # Check if this is an update and if it was already confirmed before saving
        is_new_confirmation = False
        if self.pk:
            old_instance = Payment.objects.filter(pk=self.pk).first()
            if old_instance and not old_instance.is_confirmed and self.is_confirmed:
                is_new_confirmation = True
        elif self.is_confirmed:
            is_new_confirmation = True

        super().save(*args, **kwargs)

        # If admin just confirmed this bank transfer payment, run the workflow automation!
        if is_new_confirmation:
            request_obj = self.service_request
            if request_obj.status != "paid":
                request_obj.status = "paid"
                request_obj.save()

                # Dispatch the final confirmation invoice email
                from main.brevo_email import send_brevo_email
                subject = f"Payment Confirmed – Invoice for Service: {request_obj.service.name}"
                email_content = (
                    f"Hello {request_obj.name},\n\n"
                    f"Your bank transfer payment for '{request_obj.service.name}' has been successfully verified and confirmed.\n"
                    f"Tracking Token Reference: #{request_obj.id}\n"
                    f"Amount Paid: ₦{request_obj.amount_due}\n\n"
                    "Our systems engineering desk has initialized your environment workspace tracks. We will get in touch shortly with milestone timelines.\n\n"
                    "Thank you for choosing STEM CodeMaster!"
                )
                try:
                    send_brevo_email(
                        to_email=request_obj.email,
                        subject=subject,
                        html_content=email_content
                    )
                except Exception as e:
                    print(f"!!! AUTOMATED LIFECYCLE EMAIL FAILURE: {str(e)}")

class BankDetail(models.Model):
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.bank_name} – {self.account_number}"