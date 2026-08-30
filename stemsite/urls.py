from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.http import HttpResponse

from main.sitemaps import StaticViewSitemap


sitemaps = {
    "static": StaticViewSitemap,
}


urlpatterns = [
    path('favicon.ico', lambda request: HttpResponse(status=204)),

    path(
        'sitemap.xml',
        sitemap,
        {'sitemaps': sitemaps},
        name='django.contrib.sitemaps.views.sitemap',
    ),

    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('chat/', include('chat.urls')),

    path('admin/broadcast/', include('main.urls_admin')),
    path('services/', include('services.urls')),
]