from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r'^action/', views.action_view),
    re_path(r'^append-block/', views.append_block_view),
    re_path(r'^edit-block/', views.edit_block_view),
]
