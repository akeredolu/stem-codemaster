from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),  # ✅ The real Django admin
    path('', include('main.urls')),
    path('chat/', include('chat.urls')),
    
    path('admin/broadcast/', include('main.urls_admin')), 
]

