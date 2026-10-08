from django.urls import path

from . import web_views

urlpatterns = [
    path('', web_views.dashboard, name='dashboard'),
    path('deals/', web_views.deal_list, name='deal_list'),
    path('deals/new/', web_views.deal_create, name='deal_create'),
    path('deals/<int:pk>/', web_views.deal_detail, name='deal_detail'),
    path('deals/<int:pk>/status/', web_views.deal_change_status, name='deal_change_status'),
    path('deals/<int:pk>/interactions/', web_views.deal_add_interaction, name='deal_add_interaction'),
    path('deals/<int:pk>/tasks/', web_views.deal_add_task, name='deal_add_task'),
    path('tasks/', web_views.task_list, name='task_list'),
    path('tasks/<int:pk>/complete/', web_views.task_complete, name='task_complete'),
]