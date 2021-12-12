from django.urls import path, include

urlpatterns = [
    path(r'__liveedit__/', include('liveedit.urls')),
    path(r'admin/', include('wagtail.admin.urls')),
]
