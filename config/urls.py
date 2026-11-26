from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

handler403 = 'config.views.permission_denied'
handler404 = 'config.views.page_not_found'
handler500 = 'config.views.server_error'

urlpatterns = [
    path("products/", include("products.urls")),
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
