from django.shortcuts import redirect
from django.urls import reverse
from main.models import Enrollment

class ForcePasswordChangeMiddleware:
    """
    Enforces that a student must set their password after secret code login.
    Relies on Enrollment.has_set_password instead of user.has_usable_password().
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Only enforce after secret code login
        if request.session.get("secret_logged_in", False):
            allowed_paths = [
                reverse("initial_password_set"),
                reverse("logout"),
                reverse("secret_code_login_simple"),
                "/admin/",
            ]

            # Get active enrollment from session
            enrollment_id = request.session.get("enrollment_id")
            if enrollment_id:
                try:
                    enrollment = Enrollment.objects.get(id=enrollment_id, user=request.user)
                except Enrollment.DoesNotExist:
                    enrollment = None
            else:
                enrollment = None

            # If enrollment exists and password not yet set → force redirect
            if enrollment and not enrollment.has_set_password:
                if not any(request.path_info.startswith(path) for path in allowed_paths):
                    return redirect("initial_password_set")

        return self.get_response(request)
