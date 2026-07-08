from django import forms
from .models import ServiceRequest
from .models import Payment
class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ["service", "name", "email", "phone", "details"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4, "class": "form-control form-control-lg"}),
            "name": forms.TextInput(attrs={"class": "form-control form-control-lg"}),
            "email": forms.EmailInput(attrs={"class": "form-control form-control-lg"}),
            "phone": forms.TextInput(attrs={"class": "form-control form-control-lg"}),
            "service": forms.Select(attrs={"class": "form-select form-select-lg"}),
        }


# services/forms.py
class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["proof"]
        widgets = {
            "proof": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "required": True,
                    "accept": ".jpg,.jpeg,.png,.pdf",  # optional: limit allowed file types
                }
            ),
        }
        labels = {
            "proof": "Upload Proof of Payment",
        }

    def clean_proof(self):
        proof = self.cleaned_data.get("proof")
        if proof:
            # Optional: Limit file size to 5MB
            max_size = 5 * 1024 * 1024
            if proof.size > max_size:
                raise forms.ValidationError("File size must be under 5MB.")
        return proof
