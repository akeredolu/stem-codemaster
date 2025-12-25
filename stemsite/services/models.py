# services/models.py
from django.db import models

from cloudinary_storage.storage import RawMediaCloudinaryStorage

class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.ImageField(upload_to="services/icons/", blank=True, null=True)
    brochure = models.FileField(upload_to="services/brochures/", blank=True, null=True)
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


    # Brochure forced to RAW so PDFs download correctly
    brochure = models.FileField(
        upload_to="services/brochures/",
        storage=RawMediaCloudinaryStorage(),
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


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
        related_name="payments"  # ✅ ADD THIS
    )
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    reference = models.CharField(max_length=100, blank=True)
    proof = models.FileField(upload_to="payment_proofs/", blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)



class BankDetail(models.Model):
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.bank_name} – {self.account_number}"

