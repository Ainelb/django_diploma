from django.contrib.auth.models import User
from rest_framework import generics, permissions, viewsets

from .permissions import IsAdminRole, IsHeadOrAdmin
from .serializers import MeSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ - регистрация нового менеджера."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ - текущий пользователь."""

    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ModelViewSet):
    """Список пользователей видят руководитель/админ для того, чтобы назначать менеджеров, но
    изменять роли и блокировать пользователей может только админ."""

    queryset = User.objects.select_related('profile').order_by('username')
    serializer_class = UserSerializer
    filterset_fields = ['profile__role', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsHeadOrAdmin()]
        return [IsAdminRole()]

    def perform_destroy(self, instance):
        # сделки не удаляются, а закрываются как архив для того, чтобы не потерять историю сделки
        instance.is_active = False
        instance.save(update_fields=['is_active'])