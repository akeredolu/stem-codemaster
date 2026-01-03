# views_admin.py
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
#from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags

from .forms import AdminBroadcastForm
from .models import Notification, StudentCourse, Material, Assignment, LiveSession, Course


def get_students_from_selection(course=None, students=None):
    if students:
        return students
    if course:
        sc = StudentCourse.objects.filter(course=course)
        return [s.student for s in sc]
    return []

@staff_member_required
def admin_broadcast_center(request):
    if request.method == 'POST':
        form = AdminBroadcastForm(request.POST)
        if form.is_valid():
            broadcast_type = form.cleaned_data['broadcast_type']
            course = form.cleaned_data['course']
            students = form.cleaned_data['students']
            title = form.cleaned_data['title']
            message = form.cleaned_data['message']
            related_object = form.cleaned_data['related_object']

            # determine object if selected
            obj = None
            if related_object:
                model_name, obj_id = related_object.split(':')
                model_map = {
                    'assignment': Assignment,
                    'material': CourseMaterial,
                    'live': LiveSession,
                }
                model_class = model_map.get(model_name)
                if model_class:
                    obj = model_class.objects.filter(id=obj_id).first()

            target_students = get_students_from_selection(course, students)
            total_sent = 0

            for user in target_students:
                Notification.objects.create(
                    student=user,
                    notif_type=broadcast_type,
                    title=title,
                    message=message,
                    obj_content_type=ContentType.objects.get_for_model(obj) if obj else None,
                    obj_id=obj.id if obj else None
                )

                # Send Email
                try:
                    send_email_async(
                        subject=title,
                        message=strip_tags(message),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient=[user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print("Email send error:", e)

                total_sent += 1

            messages.success(request, f"✅ Broadcast sent to {total_sent} student(s).")
            return redirect('admin_broadcast_center')
    else:
        form = AdminBroadcastForm()

    context = {
        'title': 'Admin Broadcast Center',
        'form': form,
    }
    return render(request, 'admin/broadcast_center.html', context)

