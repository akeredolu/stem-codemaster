from django import forms
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import IssueReport

from django.forms import HiddenInput 

from .models import CoursePayment, Course
from .models import Enrollment, ContactMessage, Profile


# ----------------------------
# Contact Form (ModelForm)
# ----------------------------
class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your email'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Your message'}),
        }


# ----------------------------
# Enrollment Form (Free enrollment)
# ----------------------------

# -----------------------------------
# Skill level comparison order
# -----------------------------------
# Skill level comparison order
SKILL_LEVEL_ORDER = {
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3,
}

# Courses with minimum required skill level
COURSE_MIN_LEVEL = {
    "Advance Full Stack Web Development with Django": "Advanced",
    "Full Stack Web Development with Django": "Intermediate",
    "Full Stack Web Development with Laravel": "Intermediate",
    "Robotics with Arduino Uno and Micro:bit": "Intermediate",
    # Add more if needed; courses not listed are Beginner-friendly
}

class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = [
            'full_name',
            'email',
            'program',
            'course',
            'class_type',
            'skill_level',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'program': forms.Select(attrs={'class': 'form-control'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'class_type': forms.Select(attrs={'class': 'form-control'}),
            'skill_level': forms.Select(attrs={'class': 'form-control'}),
        }

    # --- Existing clean_email() stays here ---
    def clean_email(self):
        email = self.cleaned_data.get('email')
        from django.contrib.auth import get_user_model
        User = get_user_model()
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            existing_enrol = Enrollment.objects.filter(
                user=existing_user,
                course=self.cleaned_data.get('course')
            ).first()
            if existing_enrol and existing_enrol.is_enrollment_paid:
                raise ValidationError(
                    "This email is already linked to a completed enrollment for this course."
                )
        return email

    # --- NEW: course-level locking ---
    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get("course")
        skill_level = cleaned_data.get("skill_level")

        # Fail-safe if either field missing
        if not course or not skill_level:
            return cleaned_data

        # Check if course has a minimum level
        required_level = COURSE_MIN_LEVEL.get(course)
        if required_level:
            if SKILL_LEVEL_ORDER[skill_level] < SKILL_LEVEL_ORDER[required_level]:
                raise ValidationError(
                    f"The course '{course}' requires at least {required_level} level."
                )

        return cleaned_data


# ----------------------------
# Payment Proof Form (Bank transfer proof)
# ----------------------------
class PaymentProofForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['proof_of_payment']
        widgets = {
            'proof_of_payment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    # Optionally validate file type/size:
    def clean_proof_of_payment(self):
        file = self.cleaned_data.get('proof_of_payment')
        if not file:
            raise ValidationError("Please upload a valid proof of payment.")
        if file:
            # Example: limit size to 5MB
            max_size = 5 * 1024 * 1024
            if file.size > max_size:
                raise ValidationError("File size exceeds 5MB limit.")
            # Optionally check extension:
            # ext = file.name.split('.')[-1].lower()
            # if ext not in ['jpg', 'jpeg', 'png', 'pdf']:
            #     raise ValidationError("Allowed file types: jpg, jpeg, png, pdf.")
        return file


# ----------------------------
# Profile Image Form
# ----------------------------
class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }


# ----------------------------
# User Profile Edit Form
# ----------------------------
from django import forms
from django.contrib.auth.models import User
from main.models import Profile  # Ensure this is correct

class CustomUserChangeForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Last name'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 'placeholder': 'Email'
        })
    )

    image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control'
        }),
        label='Profile Image'
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')  # image is handled separately

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop('profile', None)
        super().__init__(*args, **kwargs)
        if self.profile:
            self.fields['image'].initial = self.profile.image

    def save(self, commit=True):
        user = super().save(commit)
        if self.profile:
            image = self.cleaned_data.get('image')
            if image:
                self.profile.image = image
            if commit:
                self.profile.save()
        return user

# ----------------------------
# Student Registration Form
# ----------------------------
# main/forms.py
from django import forms
from django.contrib.auth.models import User

class StudentRegisterForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
    


# ----------------------------
# Code Login Form (if using login via code)
# ----------------------------
from django import forms
from .models import CoursePayment

class CoursePaymentForm(forms.ModelForm):
    class Meta:
        model = CoursePayment
        fields = [
            'course',
            'amount_paid',
            'payment_type',
            'payment_method',
            'session_option',
            'proof_of_payment',
        ]
        widgets = {
            'course': forms.Select(attrs={'class': 'form-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'proof_of_payment': forms.FileInput(attrs={'class': 'form-control'}),
        }



#---------------------------------------
#form for scret code login after payment
#---------------------------------------
class SecretCodeLoginForm(forms.Form):
    email_or_username = forms.CharField(
        label="Email or Full Name",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Email or Full Name"
        })
    )
    secret_code = forms.CharField(
        label="Secret Code",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter Secret Code"
        })
    )


#--------Complain Form----------------
from django import forms
from .models import Complaint

class ComplaintForm(forms.ModelForm):
    message = forms.CharField(
        label="Describe your issue",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "placeholder": "Enter your complaint here...",
            "rows": 4
        }),
        required=True
    )

    class Meta:
        model = Complaint
        fields = ['message']


#-----------Student error Form----------
class IssueReportForm(forms.ModelForm):
    class Meta:
        model = IssueReport
        fields = ['category', 'message']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        

#-----------------Newly Added-----------------
# forms.py
from django import forms
from .models import Course, Assignment, Material, LiveSession, Notification

from django.contrib.auth import get_user_model

User = get_user_model()

class AdminBroadcastForm(forms.Form):
    BROADCAST_TYPE = [
        ('message', 'Custom Message'),
        ('assignment', 'Assignment'),
        ('material', 'Material'),
        ('live', 'Live Session'),
    ]

    broadcast_type = forms.ChoiceField(choices=BROADCAST_TYPE, label="Broadcast Type")
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=False, label="Select Course")
    students = forms.ModelMultipleChoiceField(queryset=User.objects.all(), required=False, label="Specific Students")
    title = forms.CharField(max_length=200, label="Subject / Title")
    message = forms.CharField(widget=forms.Textarea, label="Message Body", required=False)
    related_object = forms.ChoiceField(choices=[], required=False, label="Attach Existing Object")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate related object dynamically
        self.fields['related_object'].choices = [('', '--- None ---')] + [
            ('assignment:' + str(a.id), f'Assignment: {a.title}') for a in Assignment.objects.all()
        ] + [
            ('material:' + str(m.id), f'Material: {m.title}') for m in CourseMaterial.objects.all()
        ] + [
            ('live:' + str(l.id), f'LiveSession: {l.title}') for l in LiveSession.objects.all()
        ]

from django import forms
from .models import Course

class AdminBroadcastForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.all(), label="Select Course")
    title = forms.CharField(max_length=200)
    content = forms.CharField(widget=forms.Textarea)
    attachment = forms.FileField(required=False)


# main/forms.py
from django import forms
from main.models import Assignment, Material, LiveSession, Course

NOTIF_CHOICES = [
    ('assignment', 'Assignment'),
    ('material', 'Material'),
    ('live', 'Live Session'),
    ('message', 'Admin Message'),
    ('general', 'General Info'),
]

class AdminNotificationForm(forms.Form):
    notif_type = forms.ChoiceField(choices=NOTIF_CHOICES, label="Notification Type")
    
    # Optional fields depending on type
    assignment = forms.ModelChoiceField(queryset=Assignment.objects.all(), required=False)
    material = forms.ModelChoiceField(queryset=Material.objects.all(), required=False)
    live_session = forms.ModelChoiceField(queryset=LiveSession.objects.all(), required=False)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=False)
    title = forms.CharField(max_length=255, required=False)
    message = forms.CharField(widget=forms.Textarea, required=False)


#-----------Assignment Form----------------
from django import forms
from django.contrib.auth import get_user_model
from .models import Assignment

User = get_user_model()

class AssignmentSendForm(forms.Form):
    assignment = forms.ModelChoiceField(
        queryset=Assignment.objects.all(),
        label="Select Assignment"
    )
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_staff=False),
        widget=forms.CheckboxSelectMultiple,
        label="Select Students"
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional message to include'}),
        required=False
    )


#---------------Assignment Submission-------------
from django import forms
from .models import AssignmentSubmission

class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'file': 'Upload your completed assignment',
        }

#--------------For Assignment Sending--------------
# main/forms.py
from django import forms
from django.contrib.auth import get_user_model
from .models import Assignment

User = get_user_model()

class AssignmentSendForm(forms.ModelForm):
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_staff=False),
        widget=forms.CheckboxSelectMultiple,
        label="Select Students"
    )
    extra_message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Optional note to students (e.g. read instructions carefully).'
        }),
        required=False,
        label="Extra Message"
    )

    class Meta:
        model = Assignment
        fields = ['course', 'title', 'instructions', 'due_date']
        widgets = {
            'instructions': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }


#--------------Assignment Admin-------------
from django import forms
from django.contrib.auth import get_user_model
from .models import Assignment

User = get_user_model()

class AssignmentAdminForm(forms.ModelForm):
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_staff=False),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select students to send this assignment to."
    )

    class Meta:
        model = Assignment
        fields = ['course', 'title', 'instructions', 'due_date', 'file', 'recipients']


#---------TimeTable AdminForm-----------
from django import forms
from django.contrib.admin.widgets import AdminDateWidget, AdminTimeWidget
from .models import Timetable, GlobalTimetable

class TimetableAdminForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = "__all__"
        widgets = {
            "date": AdminDateWidget(),
            "start_time": AdminTimeWidget(),
            "end_time": AdminTimeWidget(),
        }

class GlobalTimetableAdminForm(forms.ModelForm):
    class Meta:
        model = GlobalTimetable
        fields = "__all__"
        widgets = {
            "date": AdminDateWidget(),
            "start_time": AdminTimeWidget(),
            "end_time": AdminTimeWidget(),
        }
