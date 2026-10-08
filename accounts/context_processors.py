from .roles import get_role, is_head_or_admin

def user_role(request):

    user = getattr(request, 'user', None)
    return {'user_role': get_role(user), 'can_manage': is_head_or_admin(user)}