from rest_framework.permissions import SAFE_METHODS, IsAuthenticated

from accounts.roles import is_admin, is_head_or_admin


class ReadOnlyOrHeadAdmin(IsAuthenticated):
    """Справочники (модели авто, источники): читать могут все,
    изменять - руководитель/администратор."""

    message = 'Изменять справочники может только руководитель/администратор.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.method in SAFE_METHODS or is_head_or_admin(request.user)


class DealPermission(IsAuthenticated):
    """Удалять сделки может только администратор."""

    message = 'Удалять сделки может только администратор.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if view.action == 'destroy':
            return is_admin(request.user)
        return True