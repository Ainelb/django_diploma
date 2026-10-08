from rest_framework.permissions import IsAuthenticated

from .roles import is_admin, is_head_or_admin


class IsAdminRole(IsAuthenticated):
    message = 'Действие доступно только администратору.'

    def has_permission(self, request, view):
        return super().has_permission(request, view) and is_admin(request.user)


class IsHeadOrAdmin(IsAuthenticated):
    message = 'Действие доступно руководителю отдела/администратору.'

    def has_permission(self, request, view):
        return super().has_permission(request, view) and is_head_or_admin(request.user)