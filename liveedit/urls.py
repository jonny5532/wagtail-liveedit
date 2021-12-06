from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^action/', views.action_view),
    url(r'^append-block/', views.append_block_view),
    url(r'^edit-block/', views.edit_block_view),
]
