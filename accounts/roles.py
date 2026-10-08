"""Функции для проверки роли пользователей"""

from .models import Profile

Role = Profile.Role

def get_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return Role.ADMIN
    profile = getattr(user, 'profile', None)
    return profile.role if profile else Role.MANAGER

def is_admin(user):
    return get_role(user) == Role.ADMIN

def is_head_or_admin(user):
    return get_role(user) in (Role.HEAD, Role.ADMIN)

def is_manager(user):
    return get_role(user) == Role.MANAGER