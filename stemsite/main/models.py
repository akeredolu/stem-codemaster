from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

#from django.core.mail import send_mail
from main.utils.email_service import send_email_async


from django.urls import reverse


from django.contrib.auth import get_user_model
User = get_user_model()


class Enrollment(models.Model):
    PROGRAM_CHOICES = [
        ('In-person Program', 'In-person Program'),
        ('Online Program', 'Online Program'),
        ('Hybrid Program', 'Hybrid Program'),
    ]

    COURSE_CHOICES = [
        ('App Inventor', 'App Inventor'),
        ('Advance Full Stack Web Development with Django', 'Advance Full Stack Web Development with Django'),
        ('Robotics with Arduino Uno and Micro:bit', 'Robotics with Arduino Uno and Micro:bit'),
        ('Python Programming', 'Python Programming'),
        ('Full Stack Web Development with Django', 'Full Stack Web Development with Django'),
        ('Scratch and PictoBlox Coding', 'Scratch and PictoBlox Coding'),
        ('Frontend Web Development (HTML, CSS & JavaScript)', 'Frontend Web Development (HTML, CSS & JavaScript)'),
        ('Responsive Web Development with Bootstrap 5', 'Responsive Web Development with Bootstrap 5'),
        ('Full Stack Web Development with Laravel', 'Full Stack Web Development with Laravel'),
    ]

    CLASS_TYPE_CHOICES = [
        ('Evening / After-School Class', 'Evening / After-School Class'),
        ('Weekend Class', 'Weekend Class'),
        ('Holiday / Summer Class', 'Holiday / Summer Class'),
    ]
    
    SKILL_LEVEL_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]

    # Student details
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    
    # Always link enrolment to a real user (no more ghosts)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # safer than direct import
        on_delete=models.CASCADE,
        related_name="enrolments"
    )
    
    # Program details
    program = models.CharField(max_length=50, choices=PROGRAM_CHOICES)
    course = models.CharField(max_length=100, choices=COURSE_CHOICES)
    class_type = models.CharField(max_length=50, choices=CLASS_TYPE_CHOICES)
    skill_level = models.CharField(max_length=20,choices=SKILL_LEVEL_CHOICES,blank=False)
    
    # Secret login & password flow
    secret_code = models.CharField(max_length=20, blank=True, null=True)
    has_set_password = models.BooleanField(default=False)  # ✅ renamed
    #has_changed_password = models.BooleanField(default=False)
    is_temp_password = models.BooleanField(default=True)
    

    # Enrollment/payment fields
    payment_reference = models.CharField(max_length=100, blank=True, null=True, unique=True)
    is_enrollment_paid = models.BooleanField(default=False)  
    paid_at = models.DateTimeField(blank=True, null=True)    
    payment_method = models.CharField(max_length=50, blank=True, null=True)  
    proof_of_payment = models.FileField(upload_to='payments/', blank=True, null=True)


    # Metadata
    submitted_at = models.DateTimeField(default=timezone.now)
    is_course_activated = models.BooleanField(default=False)  
    is_active = models.BooleanField(default=True) 
    is_activation_email_sent = models.BooleanField(default=False) 
    
    
    class Meta:
        unique_together = ('user', 'course')
    
    
    def __str__(self):
        return f"{self.full_name} - {self.program} - {self.course}"
    
    
    def generate_and_set_secret_code(self):
        """
        Generate, assign, and save a secret code for this enrollment.
        Returns the generated code.
        """
        from .utils import generate_secret_code

        code = generate_secret_code().strip().upper()
        self.secret_code = code
        self.save(update_fields=["secret_code"])
        return code
    

from django.db import models

class Course(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0, help_text="Order courses appear on the page")

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order']  # Courses will appear in the order you set




class StudentCourse(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    enrolled_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"


def user_profile_picture_path(instance, filename):
    # file path for user avatars or profile pictures
    return f'profile_pics/user_{instance.user.id}/{filename}'


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    image = models.ImageField(upload_to=user_profile_picture_path, default='default.jpg')
    instructor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='students_under')
    
    
    def __str__(self):
        return f"{self.user.username}'s Profile"


# Material models.py
from django.conf import settings
from django.db import models

class Material(models.Model):
    course = models.ForeignKey(Course, related_name='materials', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='course_materials/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='received_materials', blank=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    @property
    def file_type(self):
        name = self.file.name.lower()
        if name.endswith('.pdf'):
            return 'pdf'
        elif name.endswith('.mp4'):
            return 'video'
        elif name.endswith('.docx'):
            return 'docx'
        elif name.endswith('.zip'):
            return 'zip'
        else:
            return 'other'

    # ✅ Remove the send_material_notification method entirely


#-----------Newly Adfded to Material Model----------------
    
class CoursePlan(models.Model):
    CLASS_TYPE_CHOICES = [
        ('evening', 'Evening / After-School Class'),
        ('weekend', 'Weekend Class'),
        ('holiday', 'Holiday / Summer Class'),
        ('special', 'Special Class'),
    ]

    class_type = models.CharField(max_length=20, choices=CLASS_TYPE_CHOICES, unique=True)
    description = models.TextField()
    duration = models.CharField(max_length=100)
    schedule_days = models.CharField(max_length=100)  # e.g., "Monday to Friday"
    time_slots = models.TextField(help_text="Separate multiple time slots with commas.")

    # Currently CharField for fees; consider DecimalField for real calculations:
    fee_per_session = models.CharField(max_length=50)
    fee_for_bundle = models.CharField(max_length=50)
    class_size = models.PositiveIntegerField()

    discount_siblings = models.BooleanField(default=True)
    discount_early = models.BooleanField(default=True)
    discount_group = models.BooleanField(default=True)

    def __str__(self):
        # Return human-readable name for this plan
        return dict(self.CLASS_TYPE_CHOICES).get(self.class_type, "Course Plan")


class EmailTemplate(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="A unique name for this template (e.g. contact_auto_reply)"
    )
    subject = models.CharField(max_length=255, help_text="Subject line of the email")
    body = models.TextField(
        help_text="Use placeholders like {{ name }}, {{ email }}, etc., in your template body"
    )

    def __str__(self):
        return self.name

#CoursePayment Filed
class CoursePayment(models.Model):
    PAYMENT_TYPE = [('full', 'Full Payment'), ('part', 'Part Payment')]
    PAYMENT_METHOD = [('paystack', 'Paystack'), ('bank', 'Bank Transfer')]
    SESSION_CHOICES = [
        ('session', 'One Session'),
        ('multiple', 'Multiple Sessions'),
        ('bundle', 'Bundle (10 Sessions)'),
    ]
    session_option = models.CharField(max_length=20, choices=SESSION_CHOICES, default='session')
       

    enrollment = models.ForeignKey('Enrollment', on_delete=models.CASCADE)
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    reference = models.CharField(max_length=100, unique=True)
    proof_of_payment = models.FileField(upload_to='payment_proofs/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    dashboard_blocked = models.BooleanField(default=False)  # ✅ new field

    def __str__(self):
        return f"{self.enrollment.full_name} - {self.course.title} - {self.amount_paid}"


# models.py

class BankDetails(models.Model):
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


#------------Complain Model--------------
from django.db import models
from django.contrib.auth.models import User

class Complaint(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Resolved', 'Resolved')], default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Complaint"


#----------Profile Timetable-------
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Timetable(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.CharField(max_length=100)
    date = models.DateField()  # full calendar date
    start_time = models.TimeField()
    end_time = models.TimeField()
    instructor = models.CharField(max_length=100, blank=True)
    join_link = models.URLField(blank=True)

    def __str__(self):
        return f"{self.course} - {self.date} ({self.start_time}-{self.end_time})"


class GlobalTimetable(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now) # requires: from django.utils import timezone
    start_time = models.TimeField()
    end_time = models.TimeField()
    instructor = models.CharField(max_length=100, blank=True)
    join_link = models.URLField(blank=True)


    def __str__(self):
        return f"{self.course.title} - {self.date} ({self.start_time}-{self.end_time})"


#-----------Assignment and Assinment Submission--------------
from django.db import models
from django.contrib.auth.models import User

class Assignment(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    due_date = models.DateField()
    upload_date = models.DateTimeField(auto_now_add=True)
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assignments', blank=True)
    file = models.FileField(upload_to='assignments/files/', blank=True, null=True)

    
    def __str__(self):
        return f"{self.title} - {self.course.title}"
    

class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to='assignments/submissions/')
    submitted_at = models.DateTimeField(auto_now_add=True)

    # New fields for grading/feedback
    correction_file = models.FileField(
        upload_to='assignments/corrections/',
        blank=True,
        null=True,
        help_text="Optional: Upload corrected file for student to download"
    )
    feedback_comments = models.TextField(
        blank=True,
        null=True,
        help_text="Optional: Write grading feedback"
    )

    def __str__(self):
        return f"{self.assignment.title} - {self.student.username}"

#---------------Admin Message---------------
class AdminMessage(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_messages')
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)


    def __str__(self):
        return f"To {self.student.username} - {self.title}"


#--------Students Error Report---------
class IssueReport(models.Model):
    CATEGORY_CHOICES = [
        ('bug', 'Bug / Error'),
        ('payment', 'Payment Issue'),
        ('access', 'Access Problem'),
        ('other', 'Other'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issue_reports')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Issue from {self.student.username} - {self.get_category_display()}"


#----------------LiveSession Model------------
class LiveSession(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    link = models.URLField(help_text="Paste the meeting link (Zoom, CoScreen, Google Meet, etc.)")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(blank=True, null=True)
    
    # NEW: allow admin to select specific students for this session
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True)

    reminder_sent = models.BooleanField(default=False)
    reminder_24hr_sent = models.BooleanField(default=False)
    reminder_1hr_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.course.title}"


#--------parent testimonial----------
class ParentTestimonial(models.Model):
    name = models.CharField(max_length=100)
    occupation = models.CharField(max_length=100, blank=True, null=True) 
    photo = models.ImageField(upload_to='testimonials/')
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name}'s Comment"


#-------For Enrolment fee Reciept------
class SiteSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.key}: {self.value}"


#------------------Newly Added---------------------
# models.py (append near AdminMessage or where you prefer)
class Notification(models.Model):
    """
    A lightweight notification that appears on a student's dashboard.
    Created automatically by signals when admin posts Assignment/CourseMaterial/LiveSession,
    or manually by admin.
    """
    NOTIF_TYPE = [
        ('assignment', 'Assignment'),
        ('material', 'Material'),
        ('live', 'LiveSession'),
        ('message', 'AdminMessage'),
        ('general', 'General'),
    ]
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=20, choices=NOTIF_TYPE, default='general')
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True, null=True)
    obj_content_type = models.ForeignKey('contenttypes.ContentType', null=True, blank=True, on_delete=models.SET_NULL)
    obj_id = models.PositiveIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif to {self.student.username}: {self.title}"


#------------------Newly Added About and Program Sections---------------------
from django.db import models

class AboutSection(models.Model):
    title = models.CharField(max_length=200)
    main_text = models.TextField()
    who_we_are = models.TextField()
    what_we_do = models.TextField()

    def __str__(self):
        return "About Section Content"


class ProgramIntro(models.Model):
    intro1 = models.TextField("First Paragraph")
    intro2 = models.TextField("Second Paragraph")

    def __str__(self):
        return "Programs Introduction"

class Program(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    features = models.TextField(help_text="Enter features separated by line breaks.")
    mode_of_delivery = models.CharField(max_length=300)
    class_size = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0, help_text="Order programs appear on the page")

    def feature_list(self):
        return self.features.split("\n")

    def __str__(self):
        return self.title



