from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from wagtail.core import urls as wagtail_urls

from .views import page_view

urlpatterns = [
    path('__liveedit__/', include('liveedit.urls')),
    path('admin/', include('wagtail.admin.urls')),
    path('page/', page_view),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
