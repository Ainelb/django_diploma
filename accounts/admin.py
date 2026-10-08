from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Профиль'


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ('username', 'first_name', 'last_name', 'email', 'get_role', 'is_active')

    def get_inline_instances(self, request, obj=None):

        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    @admin.display(description='Роль')
    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, 'profile') else '-'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)