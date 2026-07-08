# main/admin.py
from django.contrib import admin, messages
from django.urls import path
from django import forms
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from .models import AdminMessage
from chat.models import ChatMessage
from django.conf import settings
from .models import SiteSetting
from .models import Enrollment
from django.utils import timezone
from django.utils.timezone import localtime
from django.utils.html import format_html
from main.brevo_email import send_brevo_email

from .models import *
import logging
User = get_user_model()
logger = logging.getLogger(__name__)

# =============== FORMS ==================

# =============== ADMIN CLASSES ==================
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'avatar', 'instructor')
    search_fields = ('user__username',)


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
            # 1️⃣ Mark as paid
            enrollment.is_enrollment_paid = True
            enrollment.paid_at = timezone.now()
            enrollment.save(update_fields=["is_enrollment_paid", "paid_at"])

            # 2️⃣ Generate secret code if missing
            if not enrollment.secret_code:
                code = enrollment.generate_and_set_secret_code()
            else:
                code = enrollment.secret_code

            # 3️⃣ Send secret code email
            self.send_secret_code_email(enrollment, code)

            updated += 1

    self.message_user(
        request,
        f"{updated} enrollment(s) marked as paid and secret codes sent.",
        messages.SUCCESS,
    )


# =========================================================
# ACTION: Activate Course
# =========================================================
@admin.action(description="Activate course for selected enrollments")
def activate_course(self, request, queryset):
    updated = 0

    for enrollment in queryset:
        if not enrollment.is_course_activated:
            enrollment.is_course_activated = True
            enrollment.is_active = True
            enrollment.save(update_fields=["is_course_activated", "is_active"])

            # ✅ Send activation email only once
            if not enrollment.is_activation_email_sent:
                subject = "Your Course Has Been Activated!"
                message = (
                    f"Hello {enrollment.full_name},\n\n"
                    f"Your course '{enrollment.course}' under the '{enrollment.program}' "
                    "has been activated successfully. 🎉\n\n"
                    "You can now log in to your student portal and start learning.\n\n"
                    "Best regards,\n"
                    "STEM CodeMaster Team"
                )

                try:
                    send_brevo_email(
                        to_email=enrollment.email,
                        subject=subject,
                        html_content=f"<pre>{message}</pre>",
                    )
                    enrollment.is_activation_email_sent = True
                    enrollment.save(update_fields=["is_activation_email_sent"])
                except Exception as e:
                    logger.error(
                        f"Activation email failed for {enrollment.email}: {e}"
                    )

            updated += 1

    self.message_user(
        request,
        f"{updated} enrollment(s) activated successfully.",
        messages.SUCCESS,
    )


# =========================================================
# ACTION: Resend Secret Code
# =========================================================
@admin.action(description="Resend secret code email")
def resend_secret_code(self, request, queryset):
    sent_count = 0

    for enrollment in queryset:
        if enrollment.secret_code:
            self.send_secret_code_email(enrollment, enrollment.secret_code)
            sent_count += 1

    if sent_count:
        self.message_user(
            request,
            f"Secret code resent to {sent_count} student(s).",
            messages.SUCCESS,
        )
    else:
        self.message_user(
            request,
            "No secret codes found to resend.",
            messages.WARNING,
        )


# =========================================================
# HELPER: Send Secret Code Email (Brevo)
# =========================================================
def send_secret_code_email(self, enrollment, code):
    subject = "Your STEM CodeMaster Secret Code"
    message = (
        f"Hello {enrollment.full_name},\n\n"
        "✅ Your enrollment has been confirmed.\n\n"
        f"Here is your secret login code: {code}\n\n"
        "Use this code to log in via the secret login page.\n\n"
        "Best regards,\n"
        "STEM CodeMaster Team"
    )

    try:
        send_brevo_email(
            to_email=enrollment.email,
            subject=subject,
            html_content=f"<pre>{message}</pre>",
        )
    except Exception as e:
        logger.error(
            f"Secret code email failed for {enrollment.email}: {e}"
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
@admin.register(CoursePayment)
class CoursePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment",
        "course",
        "amount_paid",
        "payment_type",
        "payment_method",
        "is_verified",
        "dashboard_blocked",
        "proof_of_payment_link",
        "created_at",
    )

    search_fields = ("enrollment__full_name", "course__title", "reference")
    list_editable = ("is_verified",)
    list_filter = (
        "payment_type",
        "payment_method",
        "is_verified",
        "course",
        "dashboard_blocked",
    )

    readonly_fields = (
        "enrollment",
        "course",
        "amount_paid",
        "payment_type",
        "payment_method",
        "reference",
        "proof_of_payment_link",
        "created_at",
    )

    actions = ["verify_payments", "block_dashboard", "unblock_dashboard"]

    # --------------------------------------------------
    # Proof of payment link
    # --------------------------------------------------
    def proof_of_payment_link(self, obj):
        if obj.proof_of_payment:
            filename = obj.proof_of_payment.name.split("/")[-1]
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.proof_of_payment.url,
                filename,
            )
        return "-"

    proof_of_payment_link.short_description = "Proof of Payment"

    # --------------------------------------------------
    # Email helpers (Brevo)
    # --------------------------------------------------
    def send_confirmation(self, payment):
        subject = f"Payment Verified - {payment.course.title}"
        message = (
            f"Dear {payment.enrollment.full_name},\n\n"
            f"Your payment of ₦{payment.amount_paid} for the course "
            f"'{payment.course.title}' has been verified successfully.\n\n"
            "You now have full access to your learning materials.\n\n"
            "Thank you for choosing STEM CodeMaster!"
        )

        try:
            send_brevo_email(
                to_email=payment.enrollment.email,
                subject=subject,
                html_content=f"<pre>{message}</pre>",
            )
        except Exception as e:
            logger.error(
                f"Payment confirmation email failed for {payment.enrollment.email}: {e}"
            )

    # --------------------------------------------------
    # ACTION: Verify payments
    # --------------------------------------------------
    @admin.action(description="Verify selected payments")
    def verify_payments(self, request, queryset):
        updated = 0

        for payment in queryset:
            if not payment.is_verified:
                payment.is_verified = True
                payment.save(update_fields=["is_verified"])

                self.send_confirmation(payment)
                updated += 1

        self.message_user(
            request,
            f"✅ {updated} payment(s) verified successfully.",
            messages.SUCCESS,
        )

    # --------------------------------------------------
    # ACTION: Block dashboard
    # --------------------------------------------------
    @admin.action(description="Block selected student dashboard(s)")
    def block_dashboard(self, request, queryset):
        updated = 0

        for payment in queryset:
            if not payment.dashboard_blocked:
                payment.dashboard_blocked = True
                payment.save(update_fields=["dashboard_blocked"])
                updated += 1

                subject = "⚠️ Dashboard Access Restricted"
                message = (
                    f"Hello {payment.enrollment.full_name},\n\n"
                    f"Your access to the dashboard for '{payment.course.title}' "
                    "has been temporarily blocked by the admin.\n\n"
                    "Please complete your payment to regain access."
                )

                try:
                    send_brevo_email(
                        to_email=payment.enrollment.email,
                        subject=subject,
                        html_content=f"<pre>{message}</pre>",
                    )
                except Exception as e:
                    logger.error(
                        f"Dashboard block email failed for {payment.enrollment.email}: {e}"
                    )

        self.message_user(
            request,
            f"✅ {updated} student dashboard(s) blocked successfully.",
            messages.SUCCESS,
        )

    # --------------------------------------------------
    # ACTION: Unblock dashboard
    # --------------------------------------------------
    @admin.action(description="Unblock selected student dashboard(s)")
    def unblock_dashboard(self, request, queryset):
        updated = 0

        for payment in queryset:
            if payment.dashboard_blocked:
                payment.dashboard_blocked = False
                payment.save(update_fields=["dashboard_blocked"])
                updated += 1

                subject = "✅ Dashboard Access Restored"
                message = (
                    f"Hello {payment.enrollment.full_name},\n\n"
                    f"Your access to the dashboard for '{payment.course.title}' "
                    "has been restored.\n\n"
                    "You can now continue learning."
                )

                try:
                    send_brevo_email(
                        to_email=payment.enrollment.email,
                        subject=subject,
                        html_content=f"<pre>{message}</pre>",
                    )
                except Exception as e:
                    logger.error(
                        f"Dashboard unblock email failed for {payment.enrollment.email}: {e}"
                    )

        self.message_user(
            request,
            f"✅ {updated} student dashboard(s) unblocked successfully.",
            messages.SUCCESS,
        )


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


#------------------Newly Added------------------
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
    list_display = ("title", "student", "created_at", "is_archived")
    list_filter = ("is_archived", "created_at")
    search_fields = ("title", "student__username", "student__email")

    actions = ["send_message_to_selected_students"]

    # --------------------------------------------------
    # ACTION: Send Admin Message
    # --------------------------------------------------
    @admin.action(description="Send Admin Message to selected students")
    def send_message_to_selected_students(self, request, queryset):
        """
        Sends a dashboard message + notification + email to selected students.
        """

        # -------------------------------
        # Handle form submission
        # -------------------------------
        if request.method == "POST" and "apply" in request.POST:
            form = AdminMessageForm(request.POST)

            if form.is_valid():
                title = form.cleaned_data["title"]
                message_text = form.cleaned_data["message"]

                selected_ids = request.POST.getlist("_selected_action")
                students = User.objects.filter(id__in=selected_ids)

                sent_count = 0

                for student in students:
                    # 1️⃣ Save AdminMessage
                    AdminMessage.objects.create(
                        student=student,
                        title=title,
                        message=message_text,
                    )

                    # 2️⃣ Create dashboard notification
                    Notification.objects.create(
                        student=student,
                        notif_type="message",
                        title=title,
                        message=message_text,
                    )

                    # 3️⃣ Send email via Brevo
                    try:
                        send_brevo_email(
                            to_email=student.email,
                            subject=f"New Message: {title}",
                            html_content=f"""
                                <p>Hello {student.get_full_name() or student.username},</p>
                                <p>You have received a new message from the admin:</p>
                                <p><strong>{title}</strong></p>
                                <p>{message_text}</p>
                                <br>
                                <p>— STEM CodeMaster Team</p>
                            """,
                        )
                        sent_count += 1
                    except Exception:
                        # Email failure must NOT stop admin action
                        pass

                self.message_user(
                    request,
                    f"✅ Message sent to {sent_count} student(s) successfully.",
                    messages.SUCCESS,
                )

                return redirect(request.get_full_path())

        # -------------------------------
        # Initial form display
        # -------------------------------
        selected = request.POST.getlist("_selected_action") or [
            obj.pk for obj in queryset
        ]

        form = AdminMessageForm(
            initial={"_selected_action": selected}
        )

        return render(
            request,
            "admin/send_admin_message.html",
            {
                "form": form,
                "title": "Send Admin Message",
                "students": queryset,
            },
        )

# -------------------------------
# Admin Action: Send Notification
# -------------------------------
from main.models import Notification, Timetable
from .forms import AdminNotificationForm

@admin.action(description="Send Notification to Selected Students")
def send_custom_notification(modeladmin, request, queryset):
    """
    Send notifications (dashboard + email) to selected students.
    Supports: assignment, material, live session, admin message, general, timetable
    """
    if "apply" in request.POST:
        form = AdminNotificationForm(request.POST)
        if form.is_valid():
            notif_type = form.cleaned_data["notif_type"]
            assignment = form.cleaned_data.get("assignment")
            material = form.cleaned_data.get("material")
            live_session = form.cleaned_data.get("live_session")
            course = form.cleaned_data.get("course")
            title = form.cleaned_data.get("title")
            message_text = form.cleaned_data.get("message")

            for student in queryset:
                user_obj = getattr(student, "user", student)  # Ensure we have a User object

                # -------------------------------
                # Prepare title/message
                # -------------------------------
                if notif_type == "assignment" and assignment:
                    title_final = title or f"New Assignment: {assignment.title}"
                    message_final = message_text or assignment.instructions

                elif notif_type == "material" and material:
                    title_final = title or f"New Material: {material.title}"
                    message_final = message_text or material.description

                elif notif_type == "live" and live_session:
                    title_final = title or f"Upcoming Live Session: {live_session.title}"
                    message_final = message_text or (
                        f"Join link: {live_session.link}\n"
                        f"Starts at: {live_session.start_time.strftime('%d %b, %Y %I:%M %p')}"
                    )

                elif notif_type == "message":
                    title_final = title or "Message from Admin"
                    message_final = message_text or "You have received a new message from admin."

                elif notif_type == "general":
                    title_final = title or "General Notification"
                    message_final = message_text or "Important information for you."

                elif notif_type == "timetable" and course:
                    title_final = title or f"Schedule / Timetable for {course.title}"
                    timetable_entries = Timetable.objects.filter(student=user_obj, course=course)
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

                # -------------------------------
                # Save dashboard notification
                # -------------------------------
                Notification.objects.create(
                    student=user_obj,
                    notif_type=notif_type,
                    title=title_final,
                    message=message_final,
                )

                # -------------------------------
                # Send email notification via Brevo HTTP API
                # -------------------------------
                try:
                    send_brevo_email(
                        to_email=user_obj.email,
                        subject=title_final,
                        html_content=f"""
                            <p>Hello {user_obj.get_full_name() or user_obj.username},</p>
                            <p>{message_final.replace('\n', '<br>')}</p>
                            <br>
                            <p>— STEM CodeMaster Team</p>
                        """,
                    )
                except Exception:
                    # Do not block action if email fails
                    continue

            messages.success(
                request, f"✅ Notifications sent to {queryset.count()} student(s)."
            )
            return None

    else:
        form = AdminNotificationForm()

    return render(
        request,
        "admin/send_notification_form.html",
        {"students": queryset, "form": form, "title": "Send Notification"},
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
        self.message_user(
            request,
            f"{updated} enrollment(s) marked as paid and secret codes sent.",
            messages.SUCCESS
        )

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
            self.message_user(
                request,
                f"Secret code resent to {sent_count} student(s).",
                messages.SUCCESS
            )
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
        for enrollment in queryset:
            # TODO: implement your real notification logic
            pass
        self.message_user(
            request,
            f"Custom notifications sent to {queryset.count()} student(s).",
            messages.SUCCESS
        )

    # -------------------------------
    # Helper: Send Secret Code Email via Brevo
    # -------------------------------
    def send_secret_code_email(self, enrollment, code):
        subject = "Your STEM CodeMaster Secret Code"
        html_message = f"""
<p>Hello {enrollment.full_name},</p>

<p>✅ Your enrollment has been confirmed.</p>

<p>Here is your secret login code: <strong>{code}</strong></p>

<p>Use this code to log in via the secret login page.</p>

<br>
<p>Best regards,<br>STEM CodeMaster Team</p>
"""
        # Send asynchronously using Brevo HTTP API
        try:
            send_brevo_email(
                to_email=enrollment.email,
                subject=subject,
                html_content=html_message
            )
        except Exception:
            # Fallback: optionally log the error
            pass
        
#-------------Assignment---------------
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
from django.contrib.contenttypes.models import ContentType

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
            title=f"New Class TimeTable: {obj.course}",
            message=(
                f"Class '{obj.course}' scheduled on {obj.date} "
                f"from {obj.start_time.strftime('%H:%M')} to {obj.end_time.strftime('%H:%M')}. "
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
from django.contrib.contenttypes.models import ContentType
from .models import GlobalTimetable, Enrollment, Notification

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
            if not student:
                continue

            # Dashboard notification ONLY
            Notification.objects.create(
                student=student,
                notif_type="schedule",
                title=f"New Class Scheduled: {obj.course}",
                message=(
                    f"Class '{getattr(obj.course, 'title', str(obj.course))}' "
                    f"scheduled on {obj.date} from {obj.start_time.strftime('%H:%M')} "
                    f"to {obj.end_time.strftime('%H:%M')}. "
                    f"Instructor: {obj.instructor}."
                ),
                obj_content_type=ContentType.objects.get_for_model(GlobalTimetable),
                obj_id=obj.id,
            )

            notifications_sent += 1

        self.message_user(
            request,
            f"Dashboard notifications created for {notifications_sent} student(s) for {obj.course}.",
            messages.SUCCESS,
        )


#----------About and Program Sections------------------
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

