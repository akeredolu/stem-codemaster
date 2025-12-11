from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from . import views
from django.conf import settings
from django.conf.urls.static import static
from .views import submit_complaint

from .views import (
    home,
    portal,
    register,
    profile_view,  # ✅ keep only this one
    profile_change_view,
    enroll_now,
    enrolment_success,
    enrolment_payment_request,
    enrolment_payment_verify,
    upload_bank_payment_proof,
    download_material,
    payment_receipt_confirmation,
    course_payment_request,
    course_payment_verify,
    course_payment_page,
    secret_code_login_view,
    initial_password_set,
)


urlpatterns = [
    # Home & Portal
    path('', home, name='home'),
    path('portal/', portal, name='portal'),

    # Authentication: Register / Login / Logout
    path('register/', register, name='register'),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='registration/login.html'),
        name='login'
    ),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),

 
    # Profile & Profile Edit
    path('profile/', profile_view, name='profile_view'),

   

    path('profile/change/', profile_change_view, name='change_profile'),

    # Password Change & Reset
    path(
        'profile/change-password/',
        auth_views.PasswordChangeView.as_view(
            template_name='registration/password_change_form.html',
            success_url=reverse_lazy('password_change_done')
        ),
        name='password_change'
    ),
    path(
        'profile/password-changed/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='registration/password_change_done.html'
        ),
        name='password_change_done'
    ),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            success_url=reverse_lazy('password_reset_done')
        ),
        name='password_reset'
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html'
        ),
        name='password_reset_confirm'
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

    # Secret-code login (email or username)
    path('secret-login/', secret_code_login_view, name='secret_code_login_simple'),

    # First‑time set-password view (no old password required)
    path(
        'accounts/set-password/',
        initial_password_set,
        name='initial_password_set'
    ),

    # Standard change-password (old + new)
    path(
        'accounts/password_change/',
        auth_views.PasswordChangeView.as_view(
            template_name='registration/password_change_form.html'
        ),
        name='password_change'
    ),
    path(
        'accounts/password_change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='registration/password_change_done.html'
        ),
        name='password_change_done'
    ),

    # Enrollment: free form
    path('enroll/', enroll_now, name='enroll_now'),
    path('enroll/success/<int:enrollment_id>/', enrolment_success, name='enrolment_success'),
    path('payment/enrolment/initiate/<int:enrollment_id>/', enrolment_payment_request, name='enrolment_payment_request'),
    path('payment/enrolment/verify/<int:enrollment_id>/', enrolment_payment_verify, name='enrolment_payment_verify'),
    path('upload-payment-proof/<int:enrollment_id>/', upload_bank_payment_proof, name='upload_bank_payment_proof'),

    # Course payments & materials
    path('download/material/<int:material_id>/', download_material, name='download_material'),
    path('payment/receipt/<str:reference>/', payment_receipt_confirmation, name='payment_receipt'),
    path('paystack/course/<int:course_id>/', course_payment_request, name='course_payment_request'),
    path('paystack/course/verify/<str:reference>/', course_payment_verify, name='course_payment_verify'),
    #path('course/payment/', views.course_payment_page, name='course_payment'),

    #path('course/payment/<int:enrollment_id>/', views.course_payment_page, name='course_payment'),
    path('course/payment/<int:enrollment_id>/', views.course_payment_page, name='course_payment'),
    # Fallback or additional secret-code URL (if using enrollment_id)
    path('verify-login/<int:enrollment_id>/', views.verify_login_redirect, name='verify_login'),  # ✅ works after importing views
    path('complaint/submit/', submit_complaint, name='submit_complaint'),
    #path('assignments/', assignment_list, name='assignment_list'),
    #path('assignments/<int:assignment_id>/submit/', submit_assignment, name='submit_assignment'),
    path('messages/<int:message_id>/archive/', views.archive_message, name='archive_message'),
    path('report-issue/', views.report_issue, name='report_issue'),
    #path('live-sessions/create/', create_live_session, name='create_live_session'),
    #path('live-sessions/', live_session_list, name='live_session_list'),
    path('profile/', views.student_profile, name='student_profile'),
    path('assignments/submit/<int:assignment_id>/', views.submit_assignment, name='submit_assignment'),
    path('messages/archive/<int:msg_id>/', views.archive_message, name='archive_message'),

    #-----------Assignment and Submission---------
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('assignment/<int:pk>/', views.assignment_detail, name='assignment_detail'),

# ------- Students Assignment Submission ------
    path('assignments/<int:pk>/submit/', views.submit_assignment, name='submit_assignment'),

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

