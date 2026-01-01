# main/admin.py
from django.contrib import admin, messages
from django.urls import path
from django import forms
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from .models import AdminMessage
from chat.models import ChatMessage
from django.conf import settings
from django.contrib import admin
from .models import SiteSetting
from .models import Enrollment
from django.utils import timezone
from django.utils.timezone import localtime

from main.email_utils import send_email_async, send_plain_email_async
from .models import *
User = get_user_model()

# =============== FORMS ==================

# =============== ADMIN CLASSES ==================
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'avatar', 'instructor')
    search_fields = ('user__username',)


from django.contrib import admin
from .models import Course, Program, ProgramIntro, AboutSection

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "order")
    ordering = ("order",)


    # -------------------------------
    #  ACTION: Mark as Paid
    # -------------------------------
@admin.action(description="Mark selected enrollments as Paid & Send Secret Code")
def mark_enrollment_paid(self, request, queryset):
    updated = 0
    for enrollment in queryset:
        if not enrollment.is_enrollment_paid:
            # 1️⃣ Mark paid first
            enrollment.is_enrollment_paid = True
            enrollment.paid_at = timezone.now()
            enrollment.save()  # Save before generating secret code

            # 2️⃣ Generate secret code if missing
            if not enrollment.secret_code:
                code = enrollment.generate_and_set_secret_code()

                # 3️⃣ Send secret code email
                self.send_secret_code_email(enrollment, code)
            
            updated += 1

    self.message_user(
        request,
        f"{updated} enrollment(s) marked as paid and secret codes sent.",
        messages.SUCCESS
    )

 
    # -------------------------------
    #  ACTION: Activate Course
    # -------------------------------
    @admin.action(description="Activate course for selected enrollments")
    def activate_course(self, request, queryset):
        updated = 0
        for enrollment in queryset:
            if not enrollment.is_course_activated:
                enrollment.is_course_activated = True
                enrollment.is_active = True  # ensure student can log in
                enrollment.save(update_fields=["is_course_activated", "is_active"])

                # ✅ Send activation email if not already sent
                if not enrollment.is_activation_email_sent:
                    subject = "Your Course Has Been Activated!"
                    message = (
                        f"Hello {enrollment.full_name},\n\n"
                        f"Your course '{enrollment.course}' under the '{enrollment.program}' "
                        f"has been activated successfully. 🎉\n\n"
                        "You can now log in to your student portal and start learning.\n\n"
                        "Best regards,\n"
                        "STEM CodeMaster Team"
                    )
                    send_plain_email_async(
                        subject,
                        message,
                        recipients=[enrollment.email],
                        fail_silently=False,
                    )

                    enrollment.is_activation_email_sent = True
                    enrollment.save(update_fields=["is_activation_email_sent"])

                updated += 1

        self.message_user(request, f"{updated} enrollment(s) activated successfully.", messages.SUCCESS)

    # -------------------------------
    #  ACTION: Resend Secret Code
    # -------------------------------
    @admin.action(description="Resend secret code email")
    def resend_secret_code(self, request, queryset):
        sent_count = 0
        for enrollment in queryset:
            if enrollment.secret_code:
                self.send_secret_code_email(enrollment, enrollment.secret_code)
                sent_count += 1
        if sent_count:
            self.message_user(request, f"Secret code resent to {sent_count} student(s).", messages.SUCCESS)
        else:
            self.message_user(request, "No secret codes found to resend.", messages.WARNING)

    # -------------------------------
    #  HELPER: Send Secret Code Email
    # -------------------------------
    def send_secret_code_email(self, enrollment, code):
        subject = "Your STEM CodeMaster Secret Code"
        message = f"""
Hello {enrollment.full_name},

✅ Your enrollment has been confirmed.

Here is your secret login code: {code}

Use this code to log in via the secret login page.

Best regards,  
STEM CodeMaster Team
"""
        
        send_plain_email_async(
        subject=subject,
        message=message,
        recipients=[enrollment.email],  # ✅ explicit parameter
        fail_silently=False,
    )



@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at')
    search_fields = ('name', 'email', 'subject')


@admin.register(CoursePlan)
class CoursePlanAdmin(admin.ModelAdmin):
    list_display = ('class_type', 'description', 'duration', 'schedule_days', 'time_slots', 'fee_per_session', 'fee_for_bundle', 'class_size')
    search_fields = ('class_type',)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject')
    search_fields = ('name', 'subject')

# main/admin.py

from django.conf import settings
from .models import CoursePayment
from main.utils.email_utils import send_templated_email  # if you use it

@admin.register(CoursePayment)
class CoursePaymentAdmin(admin.ModelAdmin):
    list_display = (
        'enrollment',
        'course',
        'amount_paid',
        'payment_type',
        'payment_method',
        'is_verified',
        'dashboard_blocked', 
        'proof_of_payment_link',  # only the clickable link
        'created_at'
    )
    search_fields = ('enrollment__full_name', 'course__title', 'reference')
    list_editable = ('is_verified',)
    list_filter = ('payment_type', 'payment_method', 'is_verified', 'course', 'dashboard_blocked')
    readonly_fields = (
        'enrollment',
        'course',
        'amount_paid',
        'payment_type',
        'payment_method',
        'reference',
        'proof_of_payment_link',  # only the link
        'created_at'
    )

    actions = ['verify_payments', 'block_dashboard', 'unblock_dashboard']
    
    def proof_of_payment_link(self, obj):
        if obj.proof_of_payment:
            # Show filename with clickable link
            filename = obj.proof_of_payment.name.split('/')[-1]
            return format_html('<a href="{}" target="_blank">{}</a>', obj.proof_of_payment.url, filename)
        return "-"
    proof_of_payment_link.short_description = "Proof of Payment"


    # ---------- Existing verify payments ----------
    def send_confirmation(self, payment):
        subject = f"Payment Verified - {payment.course.title}"
        message = (
            f"Dear {payment.enrollment.full_name},\n\n"
            f"Your payment of ₦{payment.amount_paid} for the course "
            f"'{payment.course.title}' has been verified successfully.\n\n"
            "You now have full access to your learning materials.\n\n"
            "Thank you for choosing STEM CodeMaster!"
        )
        
        send_plain_email_async(
        subject=subject,
        message=message,
        recipients=[payment.enrollment.email],  # ✅ explicit
        fail_silently=True,
    )
        
    def verify_payments(self, request, queryset):
        updated = 0
        for payment in queryset:
            if not payment.is_verified:
                payment.is_verified = True
                payment.save()
                self.send_confirmation(payment)
                updated += 1
        self.message_user(
            request,
            f"✅ {updated} payment(s) verified successfully and confirmation emails sent.",
            level=messages.SUCCESS
        )
    verify_payments.short_description = "Verify selected payments"

    # ---------- Block dashboard ----------
    def block_dashboard(self, request, queryset):
        updated = 0
        for payment in queryset:
            if not payment.dashboard_blocked:
                payment.dashboard_blocked = True
                payment.save()
                updated += 1

                # Send notification to student
                subject = "⚠️ Dashboard Access Restricted"
                message = (
                    f"Hello {payment.enrollment.full_name},\n\n"
                    f"Your access to the dashboard for '{payment.course.title}' "
                    "has been temporarily blocked by the admin. "
                    "Please complete your payment to regain access."
                )
                try:
                    
                        # Preferred: send templated email if possible
                    send_plain_email_async(
                        to_email=payment.enrollment.user,
                        template_name="dashboard_block_notification",
                        context={"payment": payment},
                        fallback_subject=subject,
                        fallback_message=message,
                    )
                except Exception:
                    
                    send_plain_email_async(
                        subject=subject,
                        message=message,
                        recipients=[payment.enrollment.email],
                        fail_silently=True,
                    )
                    
        self.message_user(
            request,
            f"✅ {updated} student(s) dashboard(s) blocked successfully.",
            level=messages.SUCCESS
        )
    block_dashboard.short_description = "Block selected student dashboard(s)"

    # ---------- Unblock dashboard ----------
    def unblock_dashboard(self, request, queryset):
        updated = 0
        for payment in queryset:
            if payment.dashboard_blocked:
                payment.dashboard_blocked = False
                payment.save()
                updated += 1

                # Send notification to student
                subject = "✅ Dashboard Access Restored"
                message = (
                    f"Hello {payment.enrollment.full_name},\n\n"
                    f"Your access to the dashboard for '{payment.course.title}' "
                    "has been restored by the admin. You can now continue learning."
                )
                try:
                    s
                    send_plain_email_async(
                        to_email=payment.enrollment.user,
                        template_name="dashboard_unblock_notification",
                        context={"payment": payment},
                        fallback_subject=subject,
                        fallback_message=message,
                    )
                except Exception:
                    
                        # Fallback to plain text email
                    send_plain_email_async(
                        subject=subject,
                        message=message,
                        recipients=[payment.enrollment.email],
                        fail_silently=True,
                    
                    )
        self.message_user(
            request,
            f"✅ {updated} student(s) dashboard(s) unblocked successfully.",
            level=messages.SUCCESS
        )
    unblock_dashboard.short_description = "Unblock selected student dashboard(s)"



@admin.register(BankDetails)
class BankDetailsAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'account_name', 'account_number')
    search_fields = ('bank_name', 'account_name', 'account_number')


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'status', 'created_at')
    search_fields = ('user__username', 'message', 'status')


@admin.register(IssueReport)
class IssueReportAdmin(admin.ModelAdmin):
    list_display = ('student', 'category', 'message', 'submitted_at', 'is_resolved')
    search_fields = ('student__username', 'message', 'category')


@admin.register(ParentTestimonial)
class ParentTestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'occupation', 'created_at')
    search_fields = ('name', 'occupation')

#---------Enrolment Fee Reciept----------
@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value")
    search_fields = ("key",)




#------------------Newly Added-------------------

from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect, render
from django import forms
from django.contrib.auth import get_user_model

from .models import AdminMessage, Notification, Enrollment
from main.utils.email_helpers import send_broadcast_email

User = get_user_model()

#---------------------Form for Admin Broadcast--------------------
class AdminMessageForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    title = forms.CharField(max_length=200)
    message = forms.CharField(widget=forms.Textarea)

#--------------------Admin Action----------------------
@admin.register(AdminMessage)
class AdminMessageAdmin(admin.ModelAdmin):
    list_display = ('title', 'student', 'created_at', 'is_archived')
    list_filter = ('is_archived', 'created_at')
    search_fields = ('title', 'student__username', 'student__email')

    actions = ["send_message_to_selected_students"]

    def send_message_to_selected_students(self, request, queryset):
        """
        Admin selects users in User or Enrollment admin, then sends message.
        """
        if 'apply' in request.POST:
            form = AdminMessageForm(request.POST)
            if form.is_valid():
                title = form.cleaned_data['title']
                message_text = form.cleaned_data['message']
                selected_ids = request.POST.getlist('_selected_action')

                # Get students (User instances) from selected IDs
                students = User.objects.filter(id__in=selected_ids)

                for student in students:
                    # 1️⃣ Create AdminMessage record
                    AdminMessage.objects.create(
                        student=student,
                        title=title,
                        message=message_text
                    )

                    # 2️⃣ Create Dashboard Notification
                    Notification.objects.create(
                        student=student,
                        notif_type='message',
                        title=title,
                        message=message_text
                    )

                    # 3️⃣ Send Email
                    send_broadcast_email(
                        recipients_email=student.email,
                        subject=f"New Message: {title}",
                        context={"title": title, "content": message_text}
                    )

                self.message_user(request, f"Message sent to {students.count()} student(s) successfully!", level=messages.SUCCESS)
                return redirect(request.get_full_path())
        else:
            selected = request.POST.getlist('action_checkbox')         
            form = AdminMessageForm(initial={'_selected_action': selected})

        return render(request, 'admin/send_admin_message.html', {'form': form, 'title': 'Send Admin Message'})

    send_message_to_selected_students.short_description = "Send Admin Message to selected students"



from django.shortcuts import render
from main.models import Enrollment, Notification, Assignment, Material, LiveSession, Course, Timetable
from main.forms import AdminNotificationForm
from main.utils.email_helpers import send_broadcast_email

# -------------------------------
# Admin Action: Send Notification
# -------------------------------
@admin.action(description="Send Notification to Selected Students")
def send_custom_notification(modeladmin, request, queryset):
    """
    Send notifications (dashboard + email) to selected students.
    Supports: assignment, material, live session, admin message, general, timetable
    """
    if 'apply' in request.POST:
        form = AdminNotificationForm(request.POST)
        if form.is_valid():
            notif_type = form.cleaned_data['notif_type']
            assignment = form.cleaned_data.get('assignment')
            material = form.cleaned_data.get('material')
            live_session = form.cleaned_data.get('live_session')
            course = form.cleaned_data.get('course')
            title = form.cleaned_data.get('title')
            message_text = form.cleaned_data.get('message')

            for student in queryset:
                # Prepare title/message for dashboard/email
                if notif_type == 'assignment' and assignment:
                    title_final = title or f"New Assignment: {assignment.title}"
                    message_final = message_text or assignment.instructions

                elif notif_type == 'material' and material:
                    title_final = title or f"New Material: {material.title}"
                    message_final = message_text or material.description

                elif notif_type == 'live' and live_session:
                    title_final = title or f"Upcoming Live Session: {live_session.title}"
                    message_final = message_text or f"Join link: {live_session.link}\nStarts at: {live_session.start_time.strftime('%d %b, %Y %I:%M %p')}"

                elif notif_type == 'message':
                    title_final = title or "Message from Admin"
                    message_final = message_text or "You have received a new message from admin."

                elif notif_type == 'general':
                    title_final = title or "General Notification"
                    message_final = message_text or "Important information for you."

                elif notif_type == 'timetable' and course:
                    title_final = title or f"Schedule / Timetable for {course.title}"
                    timetable_entries = Timetable.objects.filter(student=student, course=course.title)
                    if timetable_entries.exists():
                        lines = [
                            f"{t.day}: {t.start_time.strftime('%H:%M')} - {t.end_time.strftime('%H:%M')} ({t.instructor})"
                            for t in timetable_entries
                        ]
                        message_final = message_text or "Course Timetable:\n" + "\n".join(lines)
                    else:
                        message_final = message_text or "No timetable set yet for this course."
                else:
                    title_final = title or "Notification"
                    message_final = message_text or "You have a new notification."

                # Save to dashboard notifications
                Notification.objects.create(
                    student=student.user,
                    notif_type=notif_type,
                    title=title_final,
                    message=message_final
                )

                # Send email notification
                send_broadcast_email(
                    s_email=student.email,
                    subject=title_final,
                    context={"title": title_final, "content": message_final}
                )

            messages.success(request, f"Notifications sent to {queryset.count()} student(s).")
            return None

    else:
        form = AdminNotificationForm()

    return render(
        request,
        "admin/send_notification_form.html",
        {"students": queryset, "form": form, "title": "Send Notification"}
    )

#-------------------testing--------------------
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "full_name", "email", "program", "skill_level", "is_enrollment_paid",
        "is_course_activated", "is_active", "is_activation_email_sent"
    )
    list_filter = ("program", "skill_level", "is_enrollment_paid", "is_course_activated", "is_active")
    search_fields = ("full_name", "email", "program", "skill_level")
    readonly_fields = ("secret_code",)

    actions = [
        "mark_enrollment_paid",
        "resend_secret_code",
        "activate_course",
        "send_custom_notification"
    ]

    # -------------------------------
    # Admin Action: Mark Paid & Send Secret Code
    # -------------------------------
    @admin.action(description="Mark selected enrollments as Paid & Send Secret Code")
    def mark_enrollment_paid(self, request, queryset):
        updated = 0
        for enrollment in queryset:
            if not enrollment.is_enrollment_paid:
                enrollment.is_enrollment_paid = True
                enrollment.paid_at = timezone.now()
                if not enrollment.secret_code:
                    code = enrollment.generate_and_set_secret_code()
                    self.send_secret_code_email(enrollment, code)
                enrollment.save()
                updated += 1
        self.message_user(request, f"{updated} enrollment(s) marked as paid and secret codes sent.", messages.SUCCESS)

    # -------------------------------
    # Admin Action: Resend Secret Code
    # -------------------------------
    @admin.action(description="Resend secret code email")
    def resend_secret_code(self, request, queryset):
        sent_count = 0
        for enrollment in queryset:
            if enrollment.secret_code:
                self.send_secret_code_email(enrollment, enrollment.secret_code)
                sent_count += 1
        if sent_count:
            self.message_user(request, f"Secret code resent to {sent_count} student(s).", messages.SUCCESS)
        else:
            self.message_user(request, "No secret codes found to resend.", messages.WARNING)

    # -------------------------------
    # Admin Action: Activate Course
    # -------------------------------
    @admin.action(description="Activate selected courses")
    def activate_course(self, request, queryset):
        activated = 0
        for enrollment in queryset:
            if not enrollment.is_course_activated:
                enrollment.is_course_activated = True
                enrollment.save()
                activated += 1
        self.message_user(request, f"{activated} course(s) activated.", messages.SUCCESS)

    # -------------------------------
    # Admin Action: Custom Notification Placeholder
    # -------------------------------
    @admin.action(description="Send custom notification")
    def send_custom_notification(self, request, queryset):
        # Example placeholder: extend this to send real notification
        for enrollment in queryset:
            # send your custom notification here
            pass
        self.message_user(request, f"Custom notifications sent to {queryset.count()} student(s).", messages.SUCCESS)

    # -------------------------------
    # Helper: Send Secret Code Email
    # -------------------------------
    def send_secret_code_email(self, enrollment, code):
        subject = "Your STEM CodeMaster Secret Code"
        message = f"""
    Hello {enrollment.full_name},

✅  Your enrollment has been confirmed.

    Here is your secret login code: {code}

    Use this code to log in via the secret login page.

    Best regards,  
    STEM CodeMaster Team
    """
        
            # Send plain email asynchronously
        send_plain_email_async(
            subject=subject,
            message=message,
            recipients=[enrollment.email],  # ✅ production-ready parameter
            fail_silently=False
        )

#-------------Assignment---------------
# main/admin.py


from django.conf import settings
from .models import Assignment, Notification
from .forms import AssignmentAdminForm

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    form = AssignmentAdminForm
    list_display = ('title', 'course', 'due_date', 'upload_date')
    search_fields = ('title', 'course__title')
    list_filter = ('course', 'due_date')
    filter_horizontal = ('recipients',)

    fieldsets = (
        (None, {
            'fields': ('course', 'title', 'instructions', 'due_date', 'file', 'recipients'),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # No more manual notifications/emails here


#-----------Assignment Submission----------------
@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'submitted_at')
    list_filter = ('assignment',)
    search_fields = ('student__username', 'assignment__title')
    readonly_fields = ('assignment', 'student', 'file', 'submitted_at')

    fieldsets = (
        (None, {
            'fields': ('assignment', 'student', 'file', 'submitted_at')
        }),
        ('Feedback', {
            'fields': ('correction_file', 'feedback_comments'),
        }),
    )



#-----------------Material------------
from django.contrib import admin
from django import forms
from .models import Material


# ---------- Admin form ----------
class MaterialAdminForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = '__all__'
        widgets = {
            'recipients': forms.SelectMultiple(attrs={
                'size': 10,
                'style': 'width: 400px;',
            }),
        }


# ---------- Admin configuration ----------
class MaterialAdmin(admin.ModelAdmin):
    form = MaterialAdminForm
    list_display = ('title', 'course', 'uploaded_at')
    search_fields = ('title', 'course__title')
    filter_horizontal = ('recipients',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Dashboard notifications & emails handled in signals
        # transaction.on_commit can be used if needed:
        # transaction.on_commit(lambda: obj.send_material_notification())


# ---------- Register ----------
admin.site.register(Material, MaterialAdmin)


#---------Live Session Admin-----------
from datetime import timedelta
from django.contrib import admin, messages
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import redirect
from django.urls import path
from main.models import LiveSession, Notification, Enrollment


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "start_time",
        "end_time",
        "reminder_24hr_sent",
        "reminder_1hr_sent",
    )
    list_filter = ("course", "start_time")
    search_fields = ("title", "course__title")
    ordering = ("-start_time",)
    filter_horizontal = ("students",)

    # Optional admin action URL (reminders only)
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "send-reminders/",
                self.admin_site.admin_view(self.send_reminders_view),
                name="send_livesession_reminders",
            ),
        ]
        return custom_urls + urls

    def send_reminders_view(self, request):
        from main.tasks import send_upcoming_live_session_reminders
        send_upcoming_live_session_reminders()
        self.message_user(
            request,
            "✅ Live session reminders queued successfully!",
            level=messages.SUCCESS,
        )
        return redirect("..")

    def save_model(self, request, obj, form, change):
        # Auto-fill end_time if missing
        if not obj.end_time and obj.start_time:
            obj.end_time = obj.start_time + timedelta(hours=1)

        super().save_model(request, obj, form, change)

        # Only notify on creation
        if change:
            return

        # Students assigned manually
        assigned_students = obj.students.all()

        # Students enrolled in the course
        enrolled_ids = Enrollment.objects.filter(
            course=obj.course, is_active=True
        ).values_list("user", flat=True)
        enrolled_students = obj.students.model.objects.filter(id__in=enrolled_ids)

        # Combine unique students
        students = set(list(assigned_students) + list(enrolled_students))

        # Dashboard notifications ONLY (no email here)
        for student in students:
            Notification.objects.create(
                student=student,
                notif_type="live_session",
                title=f"New Live Session: {obj.title}",
                message=f"A new live session '{obj.title}' has been scheduled.",
                obj_content_type=ContentType.objects.get_for_model(LiveSession),
                obj_id=obj.id,
            )

        # Admin feedback
        self.message_user(
            request,
            "Live session created and dashboard notifications sent.",
            level=messages.SUCCESS,
        )


#------------------Schedule and Time Table--------------
from django.contrib import admin, messages
from django.contrib.contenttypes.models import ContentType
from .models import Timetable, GlobalTimetable
from main.models import Notification


# ---------- Student-specific Timetable ----------
@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course",
        "date",
        "start_time",
        "end_time",
        "instructor",
        "join_link",
    )
    list_filter = ("date", "course", "student")
    search_fields = ("student__username", "course", "instructor")
    ordering = ("date", "start_time")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Only act on newly created timetable entries
        if change:
            return

        student = getattr(obj, "student", None)
        if not student:
            return

        # Dashboard notification ONLY
        Notification.objects.create(
            student=student,
            notif_type="timetable",
            title=f"New Class Scheduled: {obj.course}",
            message=(
                f"Class '{obj.course}' scheduled on {obj.date} "
                f"from {obj.start_time} to {obj.end_time}. "
                f"Instructor: {obj.instructor}."
            ),
            obj_content_type=ContentType.objects.get_for_model(Timetable),
            obj_id=obj.id,
        )

        # Admin feedback message
        student_name = getattr(student, "get_full_name", lambda: str(student))()
        self.message_user(
            request,
            f"Timetable created successfully for {student_name}.",
            messages.SUCCESS,
        )


# ------------------- Global Timetable -------------------
@admin.register(GlobalTimetable)
class GlobalTimetableAdmin(admin.ModelAdmin):
    list_display = ("course", "date", "start_time", "end_time", "instructor", "join_link")
    list_filter = ("date", "course")
    search_fields = ("course__title",)
    ordering = ("date", "start_time")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if change:
            return  # Only notify on new timetable entries

        enrollments = Enrollment.objects.filter(course=obj.course).select_related("user")
        notifications_sent = 0

        for enr in enrollments:
            student = getattr(enr, "user", None)
            if not student or not getattr(student, "email", None):
                continue

            # Dashboard notification
            Notification.objects.create(
                student=student,
                notif_type="schedule",
                title=f"New Class Scheduled: {obj.course}",
                message=(
                    f"Class '{getattr(obj.course, 'title', str(obj.course))}' "
                    f"scheduled on {obj.date} from {obj.start_time} to {obj.end_time}. "
                    f"Instructor: {obj.instructor}."
                ),
                obj_content_type=ContentType.objects.get_for_model(GlobalTimetable),
                obj_id=obj.id,
            )

            # Safe student name
            student_name = getattr(student, "get_full_name", lambda: str(student))()

            # Email notification
            send_email_async(
                to_email=student.email,
                subject="New Class Schedule Added",
                template_name="emails/timetable_notification.html",
                context={
                    "student_name": student_name,
                    "course_title": getattr(obj.course, "title", str(obj.course)),
                    "class_date": obj.date,
                    "start_time": obj.start_time,
                    "end_time": obj.end_time,
                    "instructor_name": getattr(obj.instructor, "get_full_name", lambda: str(obj.instructor))(),
                    "join_link": obj.join_link,
                },
            )

            notifications_sent += 1

        self.message_user(
            request,
            f"Notifications sent to {notifications_sent} student(s) for {obj.course}.",
            messages.SUCCESS,
        )


#----------About and Program Sections------------------
from django.contrib import admin
from .models import ProgramIntro, Program, AboutSection

# Register AboutSection
@admin.register(AboutSection)
class AboutSectionAdmin(admin.ModelAdmin):
    list_display = ("title",)
    # You can add more options if needed, like search_fields or ordering

# Register ProgramIntro
admin.site.register(ProgramIntro)

# Register Program with ordering
@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("title", "order")
    ordering = ("order",)


