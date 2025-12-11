import os
import uuid
import random
import string
import requests

from django.db.models import Q 

from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, FileResponse
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.template import Template, Context
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt


from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required

#newly added
from main.utils.user_utils import generate_unique_username

from django.contrib.auth import login, logout, authenticate, update_session_auth_hash, get_user_model
from django.contrib.auth.forms import SetPasswordForm

from .models import (
    Enrollment, Course, CoursePayment, EmailTemplate, BankDetails, CoursePlan, StudentCourse, Profile,
    Timetable, Assignment, AssignmentSubmission, AdminMessage, ParentTestimonial,
     LiveSession, Complaint, IssueReport, AboutSection, ProgramIntro, Program 
)

from .models import Timetable, GlobalTimetable, Enrollment, Course

from .forms import (
    EnrollmentForm, PaymentProofForm, ContactForm, StudentRegisterForm, CustomUserChangeForm,
    ProfileImageForm, SecretCodeLoginForm, CoursePaymentForm, IssueReportForm,
    ComplaintForm
)

#from .utils import email_notifications
from main.utils.email_utils import send_templated_email  # ✅ make sure this is imported
from main.utils.email_utils import send_payment_receipt

from chat.models import ChatMessage, ChatRoom

from . import utils  # new utils we wrote

from .utils.email_senders import send_activation_email
from main.utils import generate_secret_code
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

# -------------- HOME VIEW --------------
def home(request):
    courses = Course.objects.all()
    testimonials = ParentTestimonial.objects.all()
    course_plans = CoursePlan.objects.all().order_by('class_type')

    # NEW: Dynamic About + Program content
    about = AboutSection.objects.first()
    program_intro = ProgramIntro.objects.first()
    programs = Program.objects.all().order_by('order')  
    

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()

            # Email context
            context = {
                'name': contact.name,
                'email': contact.email,
                'subject': contact.subject,
                'message': contact.message,
            }

            # Auto-reply email
            try:
                template = EmailTemplate.objects.get(name="contact_auto_reply")
                subject = Template(template.subject).render(Context(context))
                message = Template(template.body).render(Context(context))
            except EmailTemplate.DoesNotExist:
                subject = f"Thank you for contacting us"
                message = (
                    f"Hi {contact.name},\n\n"
                    "Thanks for reaching out. We'll get back to you shortly.\n\n"
                    "Your message:\n"
                    f"{contact.message}\n\n"
                    "-STEM Codemaster Team."
                )

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[contact.email],
                fail_silently=False,
            )

            # Notify admin
            send_mail(
                subject=f"New Contact Message from {contact.name}",
                message=(
                    f"You received a new contact message:\n\n"
                    f"Name: {contact.name}\n"
                    f"Email: {contact.email}\n"
                    f"Subject: {contact.subject}\n\n"
                    f"Message:\n{contact.message}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_NOTIFICATION_EMAIL],
                fail_silently=False,
            )

            messages.success(
                request,
                "Your message has been sent successfully. A confirmation email has been sent."
            )
           
            return redirect('home')

    else:
        form = ContactForm()

    return render(request, 'base.html', {
        'form': form,
 
        'courses': courses,
        'testimonials': testimonials,
        'course_plans': course_plans,

        # NEW CONTEXT VARIABLES
        'about': about,
        'program_intro': program_intro,
        'programs': programs,
        
    })

# -------------- PORTAL VIEW --------------
@login_required
def portal(request):
    user = request.user
    enrollment = Enrollment.objects.filter(user=user).order_by('-submitted_at').first()
    enrollment_id = enrollment.id if enrollment else None

    context = {
        'enrollment_id': enrollment_id,
        # other context if needed
    }
    return render(request, 'portal/portal.html', context)


# --------------------------- REGISTER VIEW -------------------------------
def register(request):
    if request.method == "POST":
        form = StudentRegisterForm(request.POST)
        if form.is_valid():
            # 1️⃣ Create user but prevent login until password is set
            user = form.save(commit=False)
            user.set_unusable_password()
            user.save()

            # 2️⃣ Ensure profile exists and enforce password change
            profile, created = Profile.objects.get_or_create(user=user)
            profile.must_change_password = True
            profile.save()

            # 3️⃣ Store user ID in session so enrollment can attach correctly
            request.session["registered_user_id"] = user.id

            # 4️⃣ Mark in session that the student has registered
            request.session['has_registered'] = True
            request.session.set_expiry(300)  # ✅ Auto-expire after 5 minutes

            # 5️⃣ Do NOT log them in yet → they must go through secret login
            # login(request, user)  <-- intentionally removed

            # 6️⃣ Redirect to enrollment step
            return redirect("enroll_now")
    else:
        form = StudentRegisterForm()

    # Render registration page (GET or invalid POST)
    return render(request, "portal/register.html", {"form": form})


# -------------- ENROLLMENT VIEW --------------
def enroll_now(request):
    """
    Display and handle free enrollment form.
    On successful POST, save Enrollment, send confirmation email,
    and redirect to enrolment_success page.
    """

    # 1️⃣ Enforce registration before enrollment
    has_registered = request.session.get('has_registered', False)

    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        if form.is_valid():
            enrollment_data = form.cleaned_data

            # ✅ Recover user either from login or from registration session
            if request.user.is_authenticated:
                user = request.user
            else:
                user = None
                user_id = request.session.get("registered_user_id")
                if user_id:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    try:
                        user = User.objects.get(id=user_id)
                    except User.DoesNotExist:
                        user = None
                        
        # ⚠ Safeguard: never attach superuser to enrollment
                    if user and user.is_superuser:
                        messages.error(request, "Cannot create enrollment for admin or superuser accounts.")
                        return redirect('portal')

            course = enrollment_data.get("course")

            # --- SAFE Enrollment creation: always new record ---
            enrollment = Enrollment.objects.create(
                user=user,
                full_name=enrollment_data.get("full_name"),
                email=enrollment_data.get("email"),
                program=enrollment_data.get("program"),
                class_type=enrollment_data.get("class_type"),
                course=course,
                payment_reference=str(uuid.uuid4()),
                is_enrollment_paid=False,
                is_course_activated=False,
                secret_code=None,
                payment_method=None,
                paid_at=None,
            )

            created = True

            # Store enrollment ID in session for success page
            request.session['enrollment_id'] = enrollment.id  
            
            
            # ✅ Store enrollment email in session for proof upload fallback
            request.session['enrollment_email'] = enrollment.email   # <-- ADD THIS LINE

            # Reset registration flag
            if 'has_registered' in request.session:
                del request.session['has_registered']

            # Prepare context for email
            context = {
                'name': enrollment.full_name,
                'email': enrollment.email,
                'program': enrollment.program,
                'course': enrollment.course,
                'class_type': enrollment.class_type,
            }

            # Send templated email
           
            success = send_templated_email(
                student=enrollment,   # ✅ FIXED
                template_name="enrollment_confirmation",
                context=context,
                fallback_subject="Enrollment Received",
                fallback_message=(
                    f"Dear {enrollment.full_name},\n\n"
                    f"Thank you for enrolling in {enrollment.course} "
                    f"({enrollment.program}, {enrollment.class_type}).\n\n"
                    f"Please pay the ₦2,500 enrollment fee to complete your registration.\n"
                    f"Once payment is verified, your secret login code will be sent to you."
                ),
            )


            if success:
                enrollment.is_email_sent = True
                enrollment.save(update_fields=["is_email_sent"])

            # Display messages based on creation
            if created:
                messages.success(
                    request,
                    "Your enrollment has been submitted. A confirmation email has been sent."
                )
            else:
                messages.info(
                    request,
                    "You are already enrolled in this course. A confirmation email has been sent previously."
                )

            # Redirect with enrollment_id for success page
            return redirect('enrolment_success', enrollment_id=enrollment.id)

    else:
        form = EnrollmentForm()

    return render(
        request,
        'enroll_now.html',
        {'form': form, 'has_registered': has_registered}
    )


# -------------- ENROLMENT SUCCESS PAGE --------------
def enrolment_success(request, enrollment_id):
    session_id = request.session.get('enrollment_id')
    enrollment_id = session_id or enrollment_id  # ✅ fallback to URL if session empty

    if not enrollment_id:
        messages.error(request, "No enrollment found.")
        return redirect('enroll_now')

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)


    # ✅ Do not generate secret code or send login email here
    # Just show success message and payment details

    messages.success(
        request,
        f"Enrollment submitted successfully, {enrollment.full_name}! "
        "Please proceed with your payment to activate your dashboard."
    )

    return render(
        request,
        'enrolment_success.html',
        {
            'enrollment': enrollment,
            'bank_details': {
                'bank_name': 'Access Bank',
                'account_name': 'Waheed Adedayo Akeredolu',
                'account_number': '0004066568',
            }
        }
    )

# ------------------------ 1ST PART END HERE -------------------------

# -------------- PAYSTACK INITIATION FOR ENROLLMENT FEE --------------
def enrolment_payment_request(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    # Log only
    session_enroll = request.session.get('enrollment_id')
    if session_enroll != enrollment.id:
        print("⚠️ Session mismatch allowed for payment. Proceeding safely.")

    # Prevent double payment
    if enrollment.is_enrollment_paid:
        messages.info(request, "You have already paid the enrollment fee.")
        return redirect('secret_code_login_simple')

    # Amount (in kobo)
    amount_kobo = 2500 * 100  

    # Callback
    callback_url = request.build_absolute_uri(
        reverse('enrolment_payment_verify', args=[enrollment.id])
    )

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "email": enrollment.email,
        "amount": amount_kobo,  # ✅ FIXED
        "reference": enrollment.payment_reference,
        "callback_url": callback_url,
    }

    print("🚀 Initializing Paystack with:", data)

    try:
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=data,
            headers=headers,
            timeout=10
        )
        print("PAYSTACK RAW RESPONSE:", response.text)  # 🔍 Debugging
        res_data = response.json()
    except Exception as e:
        print("❌ Paystack Error:", e)
        messages.error(request, "Error initializing payment. Try again later.")
        return redirect('enrolment_success', enrollment_id=enrollment.id)

    # SUCCESS
    if res_data.get("status") and "data" in res_data:
        return redirect(res_data["data"]["authorization_url"])

    # FAILURE (No infinite loop)
    messages.error(
        request,
        f"Payment initialization failed: {res_data.get('message', 'Unknown error')}"
    )
    return redirect("enrolment_success", enrollment_id=enrollment.id)


# -------------- PAYSTACK CALLBACK/VERIFICATION FOR ENROLLMENT FEE --------------
@csrf_exempt
def enrolment_payment_verify(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    reference = request.GET.get("reference")

    if not reference:
        messages.error(request, "No payment reference provided.")
        return redirect("enrolment_success", enrollment_id=enrollment.id)

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    verify_url = f"https://api.paystack.co/transaction/verify/{reference}"

    try:
        response = requests.get(verify_url, headers=headers, timeout=10)
        result = response.json()
    except Exception:
        messages.error(request, "Error verifying payment. Please try again.")
        return redirect("enrolment_success", enrollment_id=enrollment.id)

    # ✅ Payment success
    if result.get("status") and result["data"]["status"] == "success":
        # Mark enrollment as paid
        enrollment.is_enrollment_paid = True
        enrollment.payment_method = "Paystack"
        enrollment.paid_at = timezone.now()

        # Generate and save secret code (utils only, no email here)
        secret_code = generate_secret_code().strip().upper()
        enrollment.secret_code = secret_code
        enrollment.save()

        # Link or create user if not already linked
        if not enrollment.user:
            username = generate_unique_username(enrollment.full_name, enrollment.id)
            user = User.objects.create(
                username=username,
                email=enrollment.email,
                first_name=enrollment.full_name.split()[0],
                last_name=" ".join(enrollment.full_name.split()[1:]),
            )
            user.set_unusable_password()
            user.save()

            enrollment.user = user
            enrollment.save()

        # ✅ Send secret login code email
        context = {
            "full_name": enrollment.full_name,
            "email": enrollment.email,
            "secret_code": secret_code,
        }
        
        # SAFE EMAIL SENDING (does not block payment flow)
        try:
            send_templated_email(
                enrollment,
                template_name="enrollment_payment_success",
                context={
                    'name': enrollment.full_name,
                    'program': enrollment.program,
                    'course': enrollment.course,
                    'secret_code': secret_code, 
                },
                fallback_subject="Enrollment Payment Successful",
                fallback_message=(
                    f"Hi {enrollment.full_name}, your enrollment payment was successful.\n\n"
                    f"Here is your SECRET LOGIN CODE: {secret_code}\n\n"
                    "You can now log in to access your dashboard."
                )
            )
        except Exception as e:
            print("⚠️ Email sending failed:", e)
            # Continue without raising error


        # ✅ Send payment receipt
        send_payment_receipt(enrollment)

        messages.success(
            request,
            "Enrollment fee payment successful! A secret login code has been sent to your email.",
        )
        return redirect("secret_code_login_simple")

    # ❌ Payment failed
    else:
        messages.error(request, "Payment verification failed or was not successful.")
        return redirect("enrolment_success", enrollment_id=enrollment.id)


# --------------------------- BREAK ------------------------------------

# -------------- BANK TRANSFER PROOF FOR ENROLMENT UPLOAD --------------
#@login_required
def upload_bank_payment_proof(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    # ✅ Ensure ownership via authenticated user OR session fallback
    if request.user.is_authenticated:
        if enrollment.email != request.user.email:
            messages.error(request, "This enrollment does not match your account.")
            return redirect('enrolment_success', enrollment_id=enrollment.id)
    else:
        session_email = request.session.get("enrollment_email")
        if not session_email or enrollment.email != session_email:
            messages.error(request, "You are not authorized to upload proof for this enrollment.")
            return redirect("enrolment_success", enrollment_id=enrollment.id)

    # ✅ Handle upload
    if request.method == 'POST' and request.FILES.get('proof_of_payment'):
        form = PaymentProofForm(request.POST, request.FILES, instance=enrollment)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.payment_method = 'Bank Transfer'
            # Keep is_enrollment_paid=False; admin must verify
            enrollment.save()

            # Send acknowledgement email
            send_mail(
                subject='Payment Proof Received',
                message=(
                    f"Dear {enrollment.full_name},\n\n"
                    "We have received your bank transfer proof for the ₦2,500 enrollment fee. "
                    "We will verify the payment and send you your secret code shortly."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[enrollment.email],
                fail_silently=False,
            )

            messages.success(request, "Proof uploaded. We will verify and send your secret code via email soon.")
            return redirect('secret_code_login_simple')
        else:
            messages.error(request, "Invalid file. Please upload again.")
    else:
        messages.error(request, "Failed to upload proof. Please try again.")

    return redirect('enrolment_success', enrollment_id=enrollment.id)


#--------------------------2ND PART END HERE------------------------------

#----------Course Payment View---------------
from .forms import CoursePaymentForm
from .models import Enrollment, CoursePayment, BankDetails

@login_required
def course_payment_page(request, enrollment_id):
    # Get the enrollment for this user
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user, is_active=True)

    # Bank details for display
    bank_details = BankDetails.objects.last()

    if request.method == "POST":
        # Pass POST data and FILES
        form = CoursePaymentForm(request.POST, request.FILES)

        if form.is_valid():
            payment = form.save(commit=False)
            payment.enrollment = enrollment
            payment.reference = f"CSTM-{timezone.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"

            # Bank transfer requires file
            if payment.payment_method == "bank" and not payment.proof_of_payment:
                messages.error(request, "Please upload proof of payment for bank transfer.")
                return render(request, "payments/course_payment.html", {
                    "form": form,
                    "enrollment": enrollment,
                    "bank_details": bank_details,
                })

            # Save the payment
            payment.save()

            if payment.payment_method == "paystack":
                # Redirect to Paystack with course_id and reference
                return redirect(
                    reverse("course_payment_request", kwargs={"course_id": payment.course.id}) + f"?reference={payment.reference}"
                )

            # Bank transfer: show receipt page
            return redirect("payment_receipt", reference=payment.reference)

        else:
            messages.error(request, "Please fix the errors below.")

    else:
        # For GET, pre-select the enrollment course
        form = CoursePaymentForm(initial={"course": enrollment.course})

    return render(request, "payments/course_payment.html", {
        "form": form,
        "enrollment": enrollment,
        "bank_details": bank_details,
    })

#------Email Notification with Temporary Login Details--------
def send_payment_receipt(payment):
    enrollment = payment.enrollment

    # Ensure enrollment is linked to a real user
    if not enrollment.user:
        # Generate a consistent username
        username = generate_unique_username(enrollment.full_name, enrollment.id)

        # Try to fetch existing user first
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.create(
                username=username,
                email=enrollment.email,
                first_name=enrollment.full_name.split()[0],
                last_name=" ".join(enrollment.full_name.split()[1:]) if len(enrollment.full_name.split())>1 else "",
                is_active=True
            )

        enrollment.user = user
        enrollment.save()
    else:
        user = enrollment.user

    # ✅ Generate secret code if missing
    if not enrollment.secret_code:
        code = enrollment.generate_and_set_secret_code()
        # Send secret code email
        send_secret_code_email(enrollment, code)

    # Send payment receipt email
    subject = "STEM CodeMaster - Payment Receipt"
    body = f"""
Dear {enrollment.full_name},

This is to confirm receipt of your payment of ₦{payment.amount_paid} for the course: {payment.course.title}.

Reference: {payment.reference}
Payment Type: {payment.payment_type.upper()}
Payment Method: {payment.payment_method.upper()}

Your access has been granted. Use your secret login code to log in.

Best regards,
STEM CodeMaster Team
"""
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


#----payment_receipt_confirmation------
@login_required
def payment_receipt_confirmation(request, reference):
    try:
        payment = CoursePayment.objects.get(reference=reference, enrollment__email=request.user.email)
    except CoursePayment.DoesNotExist:
        messages.error(request, "Payment not found.")
        return redirect('course_payment')

    if payment.is_verified:
        messages.success(request, "Your payment has already been confirmed.")
    else:
        messages.info(request, "Your payment has been received and is awaiting admin confirmation.")

    return render(request, 'payments/payment_receipt.html', {
        'payment': payment
    })


# ====================================
#  COURSE PAYMENT REQUEST (INITIATE)
# ====================================
@login_required
def course_payment_request(request, course_id):
    # Get course
    course = get_object_or_404(Course, id=course_id)

    # FIX: Safely get latest enrollment instead of crashing with MultipleObjectsReturned
    enrollment = Enrollment.objects.filter(
        email=request.user.email,
        course=course,
        is_active=True
    ).order_by('-id').first()

    if not enrollment:
        messages.error(request, "Enrollment record not found.")
        return redirect('courses')


    # Prevent duplicate verified payments
    if CoursePayment.objects.filter(enrollment=enrollment, course=course, is_verified=True).exists():
        messages.info(request, "You have already paid for this course.")
        return redirect('profile_view')

    # Get or create pending (unverified) payment record
    payment = CoursePayment.objects.filter(
        enrollment=enrollment,
        course=course,
        is_verified=False
    ).first()

    if not payment:
        ref = f"CPSK-{timezone.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
        payment = CoursePayment.objects.create(
            enrollment=enrollment,
            course=course,
            amount_paid=course.price,
            payment_type="full",
            payment_method="paystack",  # default
            session_option="session",
            reference=ref,
        )

    # Handle form submission
    if request.method == "POST":
        form = CoursePaymentForm(request.POST, request.FILES, instance=payment)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.save()

            # BANK TRANSFER
            if payment.payment_method == "bank":
                messages.success(request, "Bank transfer details saved. Please follow instructions to complete payment.")
                return redirect('profile_view')

            # PAYSTACK INITIALIZATION
            if payment.payment_method == "paystack":
                amount_kobo = int(payment.amount_paid * 100)
                callback_url = request.build_absolute_uri(
                    reverse('course_payment_verify', args=[payment.reference])
                )

                headers = {
                    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                }
                data = {
                    "email": enrollment.email,
                    "amount": amount_kobo,  # Correct key is "amount"
                    "reference": payment.reference,
                    "callback_url": callback_url,
                }

                try:
                    response = requests.post(
                        "https://api.paystack.co/transaction/initialize",
                        json=data,
                        headers=headers,
                        timeout=10,
                    )
                    res_data = response.json()
                    if res_data.get("status") and "authorization_url" in res_data["data"]:
                        # Redirect student to Paystack payment page
                        return redirect(res_data["data"]["authorization_url"])
                    else:
                        messages.error(request, "Failed to initiate Paystack payment. Please try again.")
                        return redirect('course_payment_request', course_id=course.id)
                except Exception:
                    messages.error(request, "Error connecting to Paystack. Please try again.")
                    return redirect('course_payment_request', course_id=course.id)
    else:
        # Initialize form without extra arguments
        form = CoursePaymentForm(instance=payment)

    bank_details = BankDetails.objects.first()
    return render(request, "payments/course_payment.html", {
        "enrollment": enrollment,
        "form": form,
        "bank_details": bank_details,
    })



# ====================================
#  COURSE PAYMENT VERIFY (CALLBACK)
# ====================================
@login_required
def course_payment_verify(request, reference):
    payment = CoursePayment.objects.filter(reference=reference).first()
    if not payment:
        messages.error(request, "Invalid or unknown payment reference.")
        return redirect('profile_view')

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    verify_url = f"https://api.paystack.co/transaction/verify/{reference}"

    try:
        response = requests.get(verify_url, headers=headers, timeout=10)
        result = response.json()
    except Exception:
        messages.error(request, "Network error verifying payment. Try again later.")
        return redirect('profile_view')

    if result.get("status") and result["data"]["status"] == "success":
        if not payment.is_verified:
            payment.is_verified = True
            payment.save()

            # ✅ Update enrollment or send receipt
            try:
                send_payment_receipt(payment)
            except Exception:
                messages.warning(request, "Payment verified but receipt email failed. Contact admin.")

        messages.success(request, "Course payment verified successfully! Receipt sent to your email.")
        return redirect('profile_view')
    else:
        messages.error(request, "Payment verification failed or not successful.")
        return redirect('profile_view')


#-------------------------3RD PART END HERE----------------------------

#--------secrect code login logic------------
def secret_code_login_view(request):
    form = SecretCodeLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data['email_or_username'].strip()
        code = ''.join(form.cleaned_data['secret_code'].split()).upper()

        enrollment = None
        user = None

        # 🔹 Try username first
        user = User.objects.filter(username__iexact=identifier).first()
        if user and user.is_superuser:
            messages.error(request, "Admin accounts cannot be used for enrollment login.")
            return redirect('secret_code_login_simple')

        # 🔹 Try user-linked enrollment
        if user:
            enrollment = Enrollment.objects.filter(
                user=user,
                secret_code__iexact=code,
                is_active=True
            ).select_related('user').first()

        # 🔹 Try email if user not found or enrollment is still missing
        if not enrollment:
            enrollment = Enrollment.objects.filter(
                email__iexact=identifier,
                secret_code__iexact=code,
                is_active=True
            ).select_related('user').first()

            # Auto-link enrollment to an existing non-admin user with same email
            if enrollment and not enrollment.user:
                existing_user = User.objects.filter(
                    email__iexact=enrollment.email,
                    is_superuser=False,
                    is_staff=False
                ).first()
                if existing_user:
                    enrollment.user = existing_user
                    enrollment.save()

        # 🔹 Try full_name fallback if still not found
        if not enrollment:
            parts = identifier.split()
            if len(parts) >= 2:
                enrollment = Enrollment.objects.filter(
                    full_name__icontains=identifier,
                    secret_code__iexact=code,
                    is_active=True
                ).select_related('user').first()

        if not enrollment:
            messages.error(request, "No enrollment found for that username, email, or name.")
            return redirect('secret_code_login_simple')

        # ✅ Ensure enrollment is linked to a user
        if not enrollment.user:
            user = User.objects.filter(email__iexact=enrollment.email, is_superuser=False).first()
            if not user:
                messages.error(request, "User account not found. Please contact support.")
                return redirect('secret_code_login_simple')
            enrollment.user = user
            enrollment.save()

        # ✅ Extra safety check for secret code
        if enrollment.secret_code.strip().upper() != code:
            messages.error(request, "Invalid secret code. Please check and try again.")
            return redirect('secret_code_login_simple')

        # ✅ Log the student in
        login(request, enrollment.user)

        # 🔹 **Set session variables** — this is the crucial fix
        request.session['secret_logged_in'] = True
        request.session['enrollment_id'] = enrollment.id

        # 🚦 Redirect to set password if first-time login
        if not enrollment.has_set_password:
            return redirect('initial_password_set')

        # ✅ Otherwise go to portal/dashboard
        return redirect('portal')
    
    print("Session enrollment_id:", request.session.get('enrollment_id'))

    # GET or invalid POST
    return render(request, "secret_code_login.html", {"form": form})


#------------Set Password View---------
def initial_password_set(request):
    enrollment_id = request.session.get('enrollment_id')

    # 🔹 Session missing or expired
    if not enrollment_id:
        messages.error(request, "Your enrollment session has expired or is invalid. Please login again.")
        return redirect('secret_code_login_simple')  # go back to secret-code login

    enrollment = Enrollment.objects.filter(id=enrollment_id).select_related('user').first()

    # 🔹 Enrollment not found or not linked to user
    if not enrollment or not enrollment.user:
        messages.error(request, "Invalid enrollment session. Please login again.")
        request.session.pop('enrollment_id', None)
        request.session.pop('secret_logged_in', None)
        return redirect('secret_code_login_simple')

    user = enrollment.user

    # 🔹 Prevent admin or already set password from accessing here
    if user.is_superuser:
        messages.error(request, "Admin accounts cannot set a student password here.")
        return redirect('portal')

    if enrollment.has_set_password:
        messages.info(request, "Your password is already set. Redirecting to portal...")
        request.session.pop('enrollment_id', None)
        request.session.pop('secret_logged_in', None)
        return redirect('portal')

    # 🔹 Initialize password form
    form = SetPasswordForm(user, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            form.save()

            # Mark enrollment as password-set
            enrollment.has_set_password = True
            enrollment.is_temp_password = False
            enrollment.save()

            # Keep user logged in
            login(request, user)
            update_session_auth_hash(request, user)

            # Clear session variables
            request.session.pop('enrollment_id', None)
            request.session.pop('secret_logged_in', None)

            messages.success(
                request,
                "✅ Your password has been set successfully! Welcome to STEM CodeMaster 🚀"
            )
            return redirect('portal')
        else:
            # Show form errors as messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
                    
                    print("Initial password_set view enrollment_id:", enrollment_id)


    # 🔹 Always render the password set template
    return render(request, 'registration/set_initial_password.html', {
        'form': form
    })


#secrete key new views
def verify_login_redirect(request, enrollment_id):
    # Optional: Store ID in session or do something with it
    return redirect('secret_code_login_simple')  # or 'secret_code_login'


def send_payment_receipt(enrollment):
    # ✅ Create or fetch user account
    if not enrollment.user:
        # Generate a consistent username only once per enrollment
        unique_username = generate_unique_username(enrollment.full_name, enrollment.id)

        # Try to get an existing user first
        user = User.objects.filter(username=unique_username).first()
        if not user:
            # Create new user
            user = User.objects.create(
                username=unique_username,
                first_name=enrollment.full_name.split()[0],
                last_name=" ".join(enrollment.full_name.split()[1:]),
                email=enrollment.email,
                is_active=True,
            )

        # Link enrollment to user
        enrollment.user = user
        enrollment.save()
    else:
        user = enrollment.user

  
    # ✅ Send payment receipt email only (no temp password)
    send_mail(
        subject="Course Payment Successful – Receipt",
        message=(
            f"Dear {enrollment.full_name},\n\n"
            f"Your payment for enrollment in {enrollment.course if isinstance(enrollment.course, str) else enrollment.course.title()} has been successfully received.\n\n"
            f"Thank you for enrolling in the {enrollment.program} program at STEM CodeMaster!\n\n"
            "-- STEM CodeMaster Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[enrollment.email],
        fail_silently=False,
    )

#---------------------------4RD PART END HERE----------------------------

# -------------- OTHER VIEWS --------------

def custom_403_view(request, exception=None):
    return render(request, '403.html', status=403)


def custom_logout(request):
    logout(request)
    messages.success(request, "You have successfully logged out.")
    return redirect('home')


#---------------------Profile View---------------------
User = get_user_model()
@login_required
def profile_view(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    complaint_form = ComplaintForm()

    # ------------------ Student Enrollments ------------------
    student_enrollments = Enrollment.objects.filter(user=user)
    enrollment = student_enrollments.first()  # Single enrollment
    
    enrolled_course_titles = student_enrollments.values_list('course', flat=True)

    enrolled_courses = Course.objects.filter(title__in=enrolled_course_titles)
    # ------------------ Enrollment existence check ------------------
    if not enrollment and not user.is_staff:
        messages.error(request, "Enrollment record not found. Please enroll first.")
        return redirect("enroll_now")
    

    # ------------------ Payment verification check ------------------
    if enrollment and not user.is_staff:
        verified_payment = CoursePayment.objects.filter(
            enrollment=enrollment,
            is_verified=True
        ).first()

    # Redirect if payment not verified
        if not verified_payment and not enrollment.is_course_activated:
            messages.warning(
                request,
                "Access denied: Please complete your course payment or wait for admin confirmation if you have paid."
            )
            payment_url = reverse("course_payment", args=[enrollment.id])
            return redirect(payment_url)

    # Redirect if dashboard is blocked
        if verified_payment and verified_payment.dashboard_blocked:
            messages.error(
                request,
                "⚠️ Your dashboard access is currently blocked. Please complete or renew your payment."
            )
            return redirect("portal")

    # ------------------ Student-Specific Content ------------------
    materials = Material.objects.filter(
        Q(course__in=enrolled_courses) | Q(recipients=user)
    ).distinct().order_by("-uploaded_at")

    assignments = Assignment.objects.filter(
        Q(course__in=enrolled_courses) | Q(recipients=user)
    ).order_by("-due_date")

    submissions = AssignmentSubmission.objects.filter(student=user)
    submission_map = {sub.assignment.id: sub for sub in submissions} if submissions else {}

    assigned_instructor = getattr(profile, "instructor", None)

    # Chat messages
    room_name = f"student_{user.username}_admin"
    room, _ = ChatRoom.objects.get_or_create(name=room_name)
    chat_messages = room.messages.all().order_by('timestamp')

    # Timetables
    timetable = Timetable.objects.filter(student=user).order_by('date', 'start_time')
    schedule = GlobalTimetable.objects.filter(course__in=enrolled_courses).order_by('date', 'start_time')

    # Admin messages
    admin_messages = AdminMessage.objects.filter(student=user, is_archived=False).order_by("-created_at")

    # Live sessions
    now = timezone.now()
    live_sessions = LiveSession.objects.filter(
        Q(course__in=enrolled_courses) | Q(students=user)
    ).distinct().order_by('start_time')

    # Payments, Complaints, Notifications
    course_payments = CoursePayment.objects.filter(enrollment__user=user)
    complaints = Complaint.objects.filter(user=user).order_by("-created_at")
    notification_list = messages.get_messages(request)

    # ------------------ Render ------------------
    return render(request, "portal/profile.html", {
        "profile": profile,
        "instructors": [assigned_instructor] if assigned_instructor else [],
        "enrollment_id": enrollment.id if enrollment else None,
        "enrolled_courses": student_enrollments,
        "materials": materials,
        "assignments": assignments,
        "submissions": submissions,
        "submission_map": submission_map,
        "complaint_form": complaint_form,
        "complaints": complaints,
        "chat_messages": chat_messages,
        "timetable": timetable,
        "schedule": schedule,
        "admin_messages": admin_messages,
        "live_sessions": live_sessions,
        "course_payments": course_payments,
        "notifications": notification_list,
        "now": now,
    })


#---Profile_change_view--------------
@login_required
def profile_change_view(request):
    user = request.user
    profile = getattr(user, 'profile', None)

    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, request.FILES, instance=user, profile=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect('portal')
    else:
        form = CustomUserChangeForm(instance=user, profile=profile)

    return render(request, 'portal/profile_change.html', {
        'form': form
    })



#----------Complain View-------------
@login_required
def submit_complaint(request):
    if request.method == 'POST':
        form = ComplaintForm(request.POST)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.user = request.user
            complaint.save()

            # --- Notify student ---
            context_student = {"student": request.user, "complaint": complaint}
            try:
                send_templated_email(
                    request.user,
                    template_name="complaint_acknowledgment",
                    context=context_student,
                    fallback_subject="✅ Complaint Received",
                    fallback_message=f"""
Hello {request.user.get_full_name() or request.user.username},

We have received your complaint:

"{complaint.message}"

Our team will review and respond shortly.
"""
                )
            except Exception:
                send_mail(
                    subject="✅ Complaint Received",
                    message=f"""
Hello {request.user.get_full_name() or request.user.username},

We have received your complaint:

"{complaint.message}"

Our team will review and respond shortly.
""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.user.email],
                    fail_silently=True,
                )

            # --- Notify admin ---
            admin_email = "code247.me@gmail.com"
            context_admin = {"student": request.user, "complaint": complaint}
            try:
                send_templated_email(
                    request.user,
                    template_name="New_Complaint_Notification",
                    context=context_admin,
                    fallback_subject=f"🚨 New Complaint from {request.user.get_full_name() or request.user.username}",
                    fallback_message=f"""
A new complaint was submitted.

Student: {request.user.get_full_name()} ({request.user.username})
Email: {request.user.email}

Complaint:
"{complaint.message}"
"""
                )
            except Exception:
                send_mail(
                    subject=f"🚨 New Complaint from {request.user.get_full_name() or request.user.username}",
                    message=f"""
A new complaint was submitted.

Student: {request.user.get_full_name()} ({request.user.username})
Email: {request.user.email}

Complaint:
"{complaint.message}"
""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=True,
                )

            messages.success(request, "✅ Your issue has been submitted. We’ll get back to you soon.")
            return redirect('portal')
        else:
            messages.error(request, "Form submission failed. Please check the fields.")
            # DEBUG: see why form is invalid
            print(form.errors)
    else:
        form = ComplaintForm()

    return render(request, 'portal/submit_complaint.html', {'complaint_form': form})


#-----------------Student Dashboard View-------------------------
@login_required
def student_profile(request):
    student = request.user
    submissions = AssignmentSubmission.objects.filter(student=student)
    enrolled_courses = StudentCourse.objects.filter(student=student)

    # grouped_course_materials - unchanged
    grouped_course_materials = {}
    for sc in enrolled_courses:
        materials = CourseMaterial.objects.filter(course=sc.course).order_by('-uploaded_at')
        grouped = defaultdict(list)
        for mat in materials:
            week = mat.uploaded_at.strftime("Week %W - %Y")
            grouped[week].append(mat)
        grouped_course_materials[sc.course.title] = dict(grouped)

    timetable = Timetable.objects.filter(student=student).order_by('day', 'start_time')
    admin_messages = AdminMessage.objects.filter(student=student, is_archived=False).order_by('-created_at')
    assignments = Assignment.objects.filter(course__in=[sc.course for sc in enrolled_courses])
    live_sessions = LiveSession.objects.filter(course__in=[sc.course for sc in enrolled_courses])
    course_payments = CoursePayment.objects.filter(enrollment__user=student)
    complaints = Complaint.objects.filter(user=student)

    # build submission_map: assignment.id -> AssignmentSubmission instance (latest)
    submission_map = {}
    for sub in submissions:
        submission_map[sub.assignment_id] = sub

    # also recent notifications
    notifications = Notification.objects.filter(student=student, is_read=False)[:20]

    context = {
        'enrolled_courses': enrolled_courses,
        'grouped_course_materials': grouped_course_materials,
        'timetable': timetable,
        'admin_messages': admin_messages,
        'assignments': assignments,
        'live_sessions': live_sessions,
        'course_payments': course_payments,
        'complaints': complaints,
        'submissions': submissions,
        'submission_map': submission_map,
        'notifications': notifications,
        'now': timezone.now(),
    }
    return render(request, 'main/profile.html', context)


#----------Achieve or Delete View-----------
@login_required
def archive_message(request, message_id):
    msg = get_object_or_404(AdminMessage, id=message_id, student=request.user)

    if not msg.is_archived:   # ✅ avoid unnecessary DB writes
        msg.is_archived = True
        msg.save()
        django_messages.success(request, "Message archived successfully.")
    else:
        django_messages.info(request, "This message was already archived.")

    return redirect('profile_view')  # 🔁 update if your profile view name differs

#----------Student Error View-------------
@login_required
def report_issue(request):
    if request.method == 'POST':
        form = IssueReportForm(request.POST)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.student = request.user
            issue.save()
            messages.success(request, "Your issue has been reported successfully.")
            return redirect('profile_view')  # or wherever you want to go
    else:
        form = IssueReportForm()

    return render(request, 'report_issue.html', {'form': form})


#---------------------Newly Added----------------------
@login_required
def dashboard(request):
    messages_qs = AdminMessage.objects.filter(student=request.user).order_by('-created_at')[:10]
    return render(request, 'main/profile.html', {'admin_messages': messages_qs})


#----------Newkly Added--------------------
# views.py
from .models import Assignment, AssignmentSubmission, AdminMessage, Notification

@login_required
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = request.user

    if request.method == 'POST' and request.FILES.get('file'):
        # Check if this student already submitted before
        existing = AssignmentSubmission.objects.filter(assignment=assignment, student=student).first()
        if existing:
            # Update previous submission
            existing.file = request.FILES['file']
            existing.submitted_at = timezone.now()
            existing.save()
            messages.success(request, '✅ Submission updated successfully.')
        else:
            # Create new submission
            AssignmentSubmission.objects.create(
                assignment=assignment,
                student=student,
                file=request.FILES['file']
            )
            messages.success(request, '🎉 Assignment submitted successfully.')

        # Optional: Notify instructor/admin
        if hasattr(assignment.course, "instructor") and assignment.course.instructor:
            msg = f"{student.get_full_name() or student.username} submitted '{assignment.title}'."
            Notification.objects.create(
                student=assignment.course.instructor,
                notif_type='general',
                title='Assignment submitted',
                message=msg
            )

        # ✅ Redirect back to student dashboard (profile)
        return redirect('profile_view')

    messages.error(request, "⚠️ No file uploaded. Please choose a file before submitting.")
    return redirect('profile_view')


@login_required
def archive_message(request, msg_id):
    msg = get_object_or_404(AdminMessage, id=msg_id, student=request.user)
    if request.method == 'POST':
        msg.is_archived = True
        msg.save(update_fields=['is_archived'])
        messages.success(request, 'Message archived.')
    return redirect('student_profile')

#-------------Assignment-------------
from .models import Assignment, AssignmentSubmission


@login_required
def student_dashboard(request):
    # ✅ Use ID-based lookup for safety
    user_id = request.user.id
    assignments = Assignment.objects.filter(recipients__id=user_id).order_by('-upload_date')

    # ✅ Submissions for this student
    submissions = AssignmentSubmission.objects.filter(student_id=user_id)
    submitted_ids = [s.assignment_id for s in submissions]

    print("Logged-in user:", request.user.username)
    print("Assignments found:", [a.title for a in assignments])

    context = {
        'assignments': assignments,
        'submitted_ids': submitted_ids,
        'now': timezone.now(),
    }
    return render(request, 'main/student_dashboard.html', context)


#----------Assignment Submission------------
from .models import Assignment, AssignmentSubmission
from .forms import AssignmentSubmissionForm

@login_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk, recipients=request.user)
    submission = AssignmentSubmission.objects.filter(assignment=assignment, student=request.user).first()

    if request.method == 'POST':
        form = AssignmentSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            # Prevent duplicate submissions
            if submission:
                messages.warning(request, "You already submitted this assignment.")
            else:
                new_submission = form.save(commit=False)
                new_submission.assignment = assignment
                new_submission.student = request.user
                new_submission.save()
                messages.success(request, "Assignment submitted successfully!")
            return redirect('assignment_detail', pk=assignment.pk)
    else:
        form = AssignmentSubmissionForm()

    return render(request, 'main/assignment_detail.html', {
        'assignment': assignment,
        'form': form,
        'submission': submission,
    })

#-------------Student Assignment Submission Dashboard---------------
from django.shortcuts import render, get_object_or_404, redirect
from .models import Assignment, AssignmentSubmission
from .forms import AssignmentSubmissionForm

@login_required
def student_assignments(request):
    assignments = Assignment.objects.filter(recipients=request.user).order_by('-upload_date')
    submissions = AssignmentSubmission.objects.filter(student=request.user)
    submitted_ids = [s.assignment.id for s in submissions]

    context = {
        'assignments': assignments,
        'submitted_ids': submitted_ids,
    }
    return render(request, 'student/assignments_list.html', context)

@login_required
def submit_assignment(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk, recipients=request.user)

    if request.method == 'POST':
        form = AssignmentSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.assignment = assignment
            submission.student = request.user
            submission.save()
            messages.success(request, "✅ Assignment submitted successfully!")
            return redirect('profile_view')

    else:
        form = AssignmentSubmissionForm()

    return render(request, 'student/submit_assignment.html', {
        'assignment': assignment,
        'form': form
    })

#------------Material view--------------
from .models import Material, Enrollment

@login_required
def student_dashboard(request):
    user = request.user

    print("\n=== DEBUG START ===")
    print(f"Logged in user: {user} (id={user.id})")
    print("Email:", user.email)
    print("Username:", user.username)
    
    print("=== DEBUG USER COMPARISON ===")
    print("Request.user username:", user.username)
    print("Request.user ID:", user.id)
    print("All users with materials assigned:")
    for m in Material.objects.all():
        for r in m.recipients.all():
            print(f"   Material: {m.title} → Recipient: {r.username} (id={r.id})")
            print("==============================")


    # Enrolled courses
    enrolled_courses = Enrollment.objects.filter(user=user)
    print(f"Total Enrollments: {enrolled_courses.count()}")
    for e in enrolled_courses:
        print(f"  - Enrolled in: {e.course} (id={e.course.id})")

    # All materials
    all_materials = Material.objects.all()
    print(f"Total Materials: {all_materials.count()}")
    for m in all_materials:
        print(f"  - Material: {m.title}, course={m.course}, recipients={[r.username for r in m.recipients.all()]}")

    # Filtered materials
    materials = Material.objects.filter(
        Q(course__in=enrolled_courses.values_list('course', flat=True)) | Q(recipients=user)
    ).distinct()

    print(f"Materials found for {user.username}: {materials.count()}")
    for m in materials:
        print(f"  ✅ {m.title}")

    print("=== DEBUG END ===\n")

    return render(request, 'portal/profile.html', {'materials': materials})


#-----------Live Session View--------------
from main.models import Enrollment, LiveSession

@login_required
def student_dashboard(request):
    user = request.user

    # All enrollments of this student
    enrolled_courses = Enrollment.objects.filter(user=user)

    # Extract the course titles (strings)
    enrolled_course_titles = enrolled_courses.values_list('course', flat=True)

    now = timezone.now()

    # Match live sessions using course title
    live_sessions = LiveSession.objects.filter(
        Q(course__title__in=enrolled_course_titles) | Q(students=user),
        Q(start_time__gte=now) | Q(end_time__gte=now)
    ).distinct().order_by('start_time')

    context = {
        'live_sessions': live_sessions,
        'now': now,
    }

    return render(request, 'portal/profile.html', context)


#-------Course tab view-----------
@login_required
def student_dashboard(request):
    user = request.user
    enrollments = Enrollment.objects.filter(user=user).select_related('course', 'instructor')

    context = {
        'enrollments': enrollments,
    }
    return render(request, 'portal/profile.html', context)


#---------For Access to Material Download after Payment-----------
@login_required
def download_material(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    enrollment = Enrollment.objects.filter(email=request.user.email, course=material.course).first()

    # ❌ Block if no enrollment
    if not enrollment:
        messages.error(request, "You are not enrolled in this course.")
        return redirect('profile_view')

    # ❌ Block if payment not verified
    if not CoursePayment.objects.filter(enrollment=enrollment, course=material.course, is_verified=True).exists():
        messages.warning(request, "Your payment has not been verified. You will gain access after confirmation.")
        return redirect('profile_view')

    # ✅ Serve the file
    if material.file and os.path.exists(material.file.path):
        return FileResponse(open(material.file.path, 'rb'), as_attachment=True)
    else:
        messages.error(request, "File not found.")
        return redirect('profile_view')
