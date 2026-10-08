from django.conf import settings
from django.db import models

class Profile(models.Model):
    """Расширение стандартного пользователя Django: роль и телефон"""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Администратор'
        HEAD = 'head', 'Руководитель отдела продаж'
        MANAGER = 'manager', "Менеджер (МОП)"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )

    role = models.CharField('Роль', max_length=20, choices=Role.choices, default=Role.MANAGER)
    phone = models.CharField('Телефон', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'
