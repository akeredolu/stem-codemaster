from django.urls import path
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    path("", views.our_services, name="our_services"),

    path(
        "thank-you/",
        TemplateView.as_view(template_name="services/thank_you.html"),
        name="services_thank_you",
    ),

    path(
        "pay/<int:service_request_id>/",
        views.pay_service,
        name="pay_service",
    ),

    path(
        "paystack/callback/<int:service_request_id>/",
        views.paystack_callback,
        name="paystack_callback",
    ),
    
    path(
    "payment/<int:service_request_id>/",
    views.payment_page,
    name="payment_page",
),

]

